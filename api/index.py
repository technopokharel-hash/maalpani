import os, json, jwt
from flask import Flask, redirect, request, jsonify, make_response
import google.generativeai as genai
import redis
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("JWT_SECRET", "super-secret-key")

# --- CONFIG ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")
KV_URL = os.environ.get("KV_URL")

# Redis Connection
r = redis.from_url(KV_URL, decode_responses=True)

# Gemini Configuration (High-limit Free Model)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('Gemini 2.5 Flash-Lite')

SYSTEM_PROMPT = "You are GURU, the AI mentor for Xavier's English School..." # (Keep your full prompt here)

# --- AUTH HELPERS ---
def get_user_from_cookie():
    token = request.cookies.get('auth_token')
    if not token: return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except: return None

# --- ROUTES ---

@app.route('/')
def home():
    username = get_user_from_cookie()
    return redirect('/index.html') if username else redirect('/login.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username, password = data.get('username'), data.get('password')
    user_data = r.hgetall(f"user:{username}")
    stored_pw = user_data.get('password')

    if stored_pw and check_password_hash(stored_pw, password):
        token = jwt.encode({
            'username': username,
            'exp': datetime.utcnow() + timedelta(days=7) # Remember for 7 days
        }, JWT_SECRET, algorithm="HS256")
        
        resp = make_response(jsonify({"message": "Login successful", "username": username}))
        # Set cookie to remember the device
        resp.set_cookie('auth_token', token, httponly=True, max_age=60*60*24*7) 
        return resp
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/chat', methods=['POST'])
def chat():
    username = get_user_from_cookie()
    if not username: return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    history_key = f"chat:{username}"
    
    # FETCH ENTIRE HISTORY for long-term memory
    raw_history = r.lrange(history_key, 0, -1) 
    chat_history = []
    for item in raw_history:
        msg = json.loads(item)
        chat_history.append({"role": msg['role'], "parts": [msg['content']]})

    # Start chat with loaded history
    chat_session = model.start_chat(history=chat_history)
    
    try:
        # We append the system prompt only to the first message if history is empty
        full_prompt = f"System: {SYSTEM_PROMPT}\nUser: {user_message}" if not chat_history else user_message
        response = chat_session.send_message(full_prompt)
        ai_message = response.text
        
        # Save to Redis for next time
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "model", "content": ai_message}))
        
        return jsonify({"reply": ai_message})
    except Exception as e:
        if "429" in str(e):
            return jsonify({"error": "Quota full. Wait 1 min."}), 429
        return jsonify({"error": str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout_api():
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.set_cookie('auth_token', '', expires=0) # Delete the device memory
    return resp