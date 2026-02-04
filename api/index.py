import os, json, jwt
from flask import Flask, redirect, request, jsonify, make_response
from flask_cors import CORS
import google.generativeai as genai
import redis
import sys
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv

# This forces Vercel to find your installed libraries correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask # ... rest of your imports

# 1. INITIALIZE & CONFIG
load_dotenv()
app = Flask(__name__)
# Enable CORS so your frontend can send cookies safely
CORS(app, supports_credentials=True)

# Using Gemini 2.5 Flash-Lite: Stable, Fast, 1000 RPD
MODEL_NAME = 'gemini-2.5-flash-lite' 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")
KV_URL = os.environ.get("KV_URL")

# Connect to Redis with string decoding enabled
r = redis.from_url(KV_URL, decode_responses=True)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# 2. GURU PERSONALITY PROMPT
SYSTEM_PROMPT = """
You are GURU (Generative Understanding & Resource Unit), the official AI mentor for Xavier's English School, Budhiganga-2, Morang.
Principal: Paresh Pokharel | Vice Principal: Janak Dakhal.
Chairperson: Sarita Rana Magar.
Features: Computer Lab, Math Lab, Robotics Lab, 4 Houses, 16 Clubs.
Goal: Be helpful, encourage robotics and learning, and never give direct answers—guide students to think!
"""

# 3. AUTHENTICATION HELPERS
def get_user_from_cookie():
    """Checks if the user has a valid login session on this device."""
    token = request.cookies.get('auth_token')
    if not token: return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except: return None

# 4. PRIMARY ROUTES
@app.route('/')
def home():
    """Redirects to chat if logged in, otherwise to login page."""
    username = get_user_from_cookie()
    return redirect('/index.html') if username else redirect('/login.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username, password = data.get('username'), data.get('password')
    if r.exists(f"user:{username}"):
        return jsonify({"error": "Username taken"}), 400
    
    hashed_pw = generate_password_hash(password)
    r.hset(f"user:{username}", mapping={"password": hashed_pw})
    return jsonify({"message": "Signup successful"}), 201

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
        
        resp = make_response(jsonify({"username": username, "redirect": "/index.html"}))
        # Secure Cookie to remember the user on this device
        resp.set_cookie('auth_token', token, httponly=True, samesite='Lax', max_age=60*60*24*7)
        return resp
    
    return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/chat', methods=['POST'])
def chat():
    username = get_user_from_cookie()
    if not username: return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    history_key = f"chat:{username}"
    
    # LONG-TERM MEMORY: Fetch the last 20 messages from Redis
    raw_history = r.lrange(history_key, -20, -1) 
    chat_history = []
    for item in raw_history:
        msg = json.loads(item)
        chat_history.append({"role": msg['role'], "parts": [msg['content']]})

    chat_session = model.start_chat(history=chat_history)
    
    try:
        # Include System Prompt in the very first message context
        full_input = f"System: {SYSTEM_PROMPT}\nUser: {user_message}" if not chat_history else user_message
        response = chat_session.send_message(full_input)
        ai_reply = response.text
        
        # Save both messages to Redis for history
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "model", "content": ai_reply}))
        
        return jsonify({"reply": ai_reply})
    except Exception as e:
        # Catch rate limits or API errors gracefully
        if "429" in str(e):
            return jsonify({"error": "GURU is busy. Try again in 1 minute."}), 429
        return jsonify({"error": str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.set_cookie('auth_token', '', expires=0) # Clear the device memory
    return resp

if __name__ == '__main__':
    app.run(debug=True)

    # Vercel looks for 'app' or 'handler'
handler = app