import os, json, jwt, sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- VERCEL PATH & IMPORT FIX ---
# Adds the current directory to path to ensure school_data.py is found
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from school_data import get_guru_prompt
except ImportError:
    # Fallback if school_data.py is missing or incorrectly pathed
    def get_guru_prompt(): return "You are GURU, a helpful school assistant."

# --- INITIALIZE ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# MODEL SETTINGS
MODEL_NAME = 'llama-3.3-70b-versatile'

# Import OpenAI & Redis safely to avoid crash if packages fail to install
try:
    from openai import OpenAI
    import redis
    
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY")
    )
    r = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
except Exception as e:
    print(f"Startup Warning: {e}")
    client = None
    r = None

JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")

# --- AUTH HELPERS ---
def get_user_from_cookie():
    token = request.cookies.get('token') # Changed from 'auth_token' to match standard
    if not token: return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except: return None

# --- ROUTES ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not client or not r:
        return jsonify({"error": "System services (AI or Database) are offline"}), 500

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

# Keep your Signup/Login/Logout routes below...

# IMPORTANT: Vercel needs this 'app' object
# No changes needed here.