import os, json, jwt, sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Path fix for Vercel
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from school_data import get_guru_prompt
except ImportError:
    def get_guru_prompt(): return "You are GURU, the school AI mentor."

load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_2026_key")
MODEL_NAME = "gpt-4o-mini"

# --- LAZY SERVICES (Prevents Startup Crashes) ---
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

# --- AUTH HELPERS ---
def get_user():
    token = request.cookies.get('token')
    if not token: return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])['username']
    except: return None

# --- ROUTES ---

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ready", "service": "GURU-OpenAI"}), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    username = get_user()
    if not username: return jsonify({"error": "Unauthorized"}), 401
    
    user_input = request.json.get('message')
    if not user_input: return jsonify({"error": "Empty message"}), 400

    try:
        ai = get_openai()
        r = get_redis()
        history_key = f"chat:{username}"
        
        # Build prompt
        messages = [{"role": "system", "content": get_guru_prompt()}]
        
        # Add history
        try:
            history = r.lrange(history_key, -6, -1)
            for m in history:
                msg_data = json.loads(m)
                messages.append({"role": msg_data['role'], "content": msg_data['content']})
        except: pass

        messages.append({"role": "user", "content": user_input})

        # OpenAI API Call
        response = ai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        
        reply = response.choices[0].message.content

        # Save to Redis
        r.rpush(history_key, json.dumps({"role": "user", "content": user_input}))
        r.rpush(history_key, json.dumps({"role": "assistant", "content": reply}))
        r.ltrim(history_key, -20, -1) 

        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add your Signup/Login logic here using 'get_redis()' for the 'r' client
handler = app