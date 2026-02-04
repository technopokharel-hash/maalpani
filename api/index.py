import os
import json
import sys
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

# Third-party imports are wrapped so Vercel doesn't crash at import-time.
try:
    import jwt  # pyjwt
except Exception:  # pragma: no cover
    jwt = None

try:
    import redis
except Exception:  # pragma: no cover
    redis = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

try:
    from werkzeug.security import generate_password_hash, check_password_hash
except Exception:  # pragma: no cover
    generate_password_hash = None
    check_password_hash = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

# 1. ROBUST PATH FIX (Prevents crashes from missing local modules)
# This adds the current directory to sys.path so 'school_data' can always be found.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from school_data import get_guru_prompt
except ImportError:
    # Fallback for different Vercel directory structures
    from .school_data import get_guru_prompt

# 2. INITIALIZE & CONFIG
if load_dotenv:
    load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

MODEL_NAME = 'llama-3.3-70b-versatile'

# Ensure the client only initializes if the API key exists
GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = None
if GROQ_KEY and OpenAI:
    try:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_KEY,
        )
    except Exception:
        # Avoid import-time crash if OpenAI client init fails in serverless
        client = None

JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")
KV_URL = os.environ.get("KV_URL")
try:
    r = redis.from_url(KV_URL, decode_responses=True) if (KV_URL and redis) else None
except Exception:
    # Avoid hard crash on cold start if Redis is misconfigured
    r = None

def error_response(message, status=400):
    return jsonify({"error": message}), status

def is_prod():
    return os.environ.get("VERCEL", "").lower() == "1" or os.environ.get("ENV", "").lower() == "production"

def get_user_from_cookie():
    token = request.cookies.get("token")
    if not token:
        return None
    if jwt is None:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("username")
    except Exception:
        return None

def issue_token(username):
    if jwt is None:
        raise RuntimeError("pyjwt is not installed on the server")
    exp = datetime.utcnow() + timedelta(days=7)
    return jwt.encode({"username": username, "exp": exp}, JWT_SECRET, algorithm="HS256")

def set_auth_cookie(resp, token):
    resp.set_cookie(
        "token",
        token,
        httponly=True,
        secure=is_prod(),
        samesite="Lax",
        max_age=7 * 24 * 60 * 60,
        path="/"
    )
    return resp

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "has_groq_key": bool(GROQ_KEY),
        "redis_connected": r is not None
    })

@app.route('/api/signup', methods=['POST'])
def signup():
    if generate_password_hash is None:
        return error_response("Server misconfigured: werkzeug is missing", 500)
    if r is None:
        return error_response("Storage unavailable: KV_URL not configured", 500)

    data = request.get_json(force=True) or {}
    username = (data.get('username') or "").strip().lower()
    password = (data.get('password') or "").strip()

    if not username or not password:
        return error_response("Username and password are required", 400)

    if r.hexists("users", username):
        return error_response("User already exists", 409)

    r.hset("users", username, generate_password_hash(password))
    return jsonify({"message": "Account created"})

@app.route('/api/login', methods=['POST'])
def login():
    if check_password_hash is None:
        return error_response("Server misconfigured: werkzeug is missing", 500)
    if jwt is None:
        return error_response("Server misconfigured: pyjwt is missing", 500)
    if r is None:
        return error_response("Storage unavailable: KV_URL not configured", 500)

    data = request.get_json(force=True) or {}
    username = (data.get('username') or "").strip().lower()
    password = (data.get('password') or "").strip()

    if not username or not password:
        return error_response("Username and password are required", 400)

    stored_hash = r.hget("users", username)
    if not stored_hash or not check_password_hash(stored_hash, password):
        return error_response("Invalid credentials", 401)

    token = issue_token(username)
    resp = make_response(jsonify({"message": "Logged in"}))
    return set_auth_cookie(resp, token)

@app.route('/api/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.delete_cookie("token", path="/")
    return resp

@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_KEY:
        return error_response("Missing GROQ_API_KEY configuration", 500)
    if OpenAI is None:
        return error_response("Server misconfigured: openai package missing", 500)
    if client is None:
        return error_response("AI client failed to initialize (check GROQ_API_KEY)", 500)

    if r is None:
        return error_response("Storage unavailable: KV_URL not configured", 500)

    username = get_user_from_cookie()
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    user_message = (request.json or {}).get('message')
    if not user_message:
        return error_response("Message is required", 400)

    history_key = f"chat:{username}"
    
    # SYSTEM PROMPT
    messages = [{"role": "system", "content": get_guru_prompt()}]
    
    # FETCH HISTORY (Wrapped in try/except to prevent crash if Redis lags)
    try:
        raw_history = r.lrange(history_key, -10, -1) 
        for item in raw_history:
            msg = json.loads(item)
            role = "assistant" if msg['role'] == "model" else "user"
            messages.append({"role": role, "content": msg['content']})
    except Exception:
        pass # Continue without history if Redis fails

    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )
        
        ai_reply = completion.choices[0].message.content
        
        # SAVE TO REDIS
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "model", "content": ai_reply}))
        
        return jsonify({"reply": ai_reply})

    except Exception as e:
        # Returns exact error to frontend for easier debugging
        return jsonify({"error": str(e)}), 500


# Vercel Python runtime sometimes looks for a WSGI callable named `handler`.
# Exporting it explicitly makes deployments more reliable.
handler = app