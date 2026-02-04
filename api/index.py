import os, json, jwt, sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- VERCEL PATH & IMPORT FIX ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from school_data import get_guru_prompt
except ImportError:
    def get_guru_prompt(): return "You are GURU, a helpful school assistant."

# --- INITIALIZE ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

MODEL_NAME = 'llama-3.3-70b-versatile'
JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")

# Global variables for Lazy Loading
_client = None
_r = None

def get_ai_client():
    """Lazily initializes the OpenAI client only when needed."""
    global _client
    if _client is None:
        try:
            from openai import OpenAI
            _client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=os.environ.get("GROQ_API_KEY")
            )
        except Exception as e:
            print(f"AI Init Error: {e}")
    return _client

def get_redis_client():
    """Lazily initializes Redis only when needed."""
    global _r
    if _r is None:
        try:
            import redis
            _r = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
        except Exception as e:
            print(f"Redis Init Error: {e}")
    return _r

# --- AUTH HELPERS ---
def get_user_from_cookie():
    token = request.cookies.get('token')
    if not token: return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except: return None

# --- ROUTES ---

@app.route('/api/ping', methods=['GET'])
def ping():
    """Tailored Plan Step 1: Frontend calls this to 'wake up' the function."""
    return jsonify({
        "status": "online",
        "timestamp": datetime.utcnow().isoformat(),
        "ready": True
    }), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    client = get_ai_client()
    r = get_redis_client()
    
    if not client or not r:
        return jsonify({"error": "GURU is still waking up. Please try again in 5 seconds."}), 503

    username = get_user_from_cookie()
    if not username: return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    history_key = f"chat:{username}"
    
    messages = [{"role": "system", "content": get_guru_prompt()}]
    
    # History Handling
    try:
        raw_history = r.lrange(history_key, -10, -1)
        for item in raw_history:
            msg = json.loads(item)
            role = "assistant" if msg['role'] == "model" else "user"
            messages.append({"role": role, "content": msg['content']})
    except: pass

    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7
        )
        ai_reply = completion.choices[0].message.content
        
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "model", "content": ai_reply}))
        
        return jsonify({"reply": ai_reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Placeholder for your existing Signup/Login/Logout routes
# Use the same 'get_redis_client()' inside those routes too!

# Vercel entry point
handler = app