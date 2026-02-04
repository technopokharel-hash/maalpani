import os, json, jwt, sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- VERCEL PATH FIX ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from school_data import get_guru_prompt
except ImportError:
    def get_guru_prompt(): return "You are GURU, the school AI mentor."

load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Config from Environment Variables
JWT_SECRET = os.environ.get("JWT_SECRET")
MODEL_NAME = "gpt-4o-mini"

# --- LAZY SERVICES ---
_openai_client = None
_redis_client = None

def get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai_client

def get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
    return _redis_client

# --- ROUTES ---

@app.route('/api/chat', methods=['POST'])
def chat():
    # 1. Check Auth
    token = request.cookies.get('token')
    if not token: return jsonify({"error": "Unauthorized"}), 401
    try:
        username = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])['username']
    except: return jsonify({"error": "Session expired"}), 401

    # 2. Get AI & DB
    try:
        ai = get_openai()
        r = get_redis()
        user_input = request.json.get('message')
        history_key = f"chat:{username}"
        
        # Build prompt + last 5 messages
        messages = [{"role": "system", "content": get_guru_prompt()}]
        try:
            history = r.lrange(history_key, -5, -1)
            for m in history:
                d = json.loads(m)
                messages.append({"role": d['role'], "content": d['content']})
        except: pass

        messages.append({"role": "user", "content": user_input})

        # OpenAI Call
        response = ai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        reply = response.choices[0].message.content

        # Save History
        r.rpush(history_key, json.dumps({"role": "user", "content": user_input}))
        r.rpush(history_key, json.dumps({"role": "assistant", "content": reply}))
        r.ltrim(history_key, -20, -1)

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Entry point for Vercel
handler = app