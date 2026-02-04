import os, json, jwt
from flask import Flask, redirect, request, jsonify, make_response
from flask_cors import CORS
from openai import OpenAI  # Standard for Groq compatibility
import redis
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from .school_data import get_guru_prompt

# 1. INITIALIZE & CONFIG
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# MODEL SETTINGS
# llama-3.3-70b-versatile is the high-quality model (1,000 requests/day)
MODEL_NAME = 'llama-3.3-70b-versatile' 

# 2. GROQ CLIENT SETUP
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY")
)

JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")
KV_URL = os.environ.get("KV_URL")
r = redis.from_url(KV_URL, decode_responses=True)

# 3. AUTHENTICATION HELPERS
def get_user_from_cookie():
    token = request.cookies.get('auth_token')
    if not token: return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except: return None

# 4. PRIMARY ROUTES
@app.route('/')
def home():
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
            'exp': datetime.utcnow() + timedelta(days=7)
        }, JWT_SECRET, algorithm="HS256")
        
        resp = make_response(jsonify({"username": username, "redirect": "/index.html"}))
        resp.set_cookie('auth_token', token, httponly=True, samesite='Lax', max_age=60*60*24*7)
        return resp
    
    return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/chat', methods=['POST'])
def chat():
    username = get_user_from_cookie()
    if not username: return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    history_key = f"chat:{username}"
    
    # SYSTEM PROMPT
    messages = [{"role": "system", "content": get_guru_prompt()}]
    
    # FETCH HISTORY (Last 10 messages)
    raw_history = r.lrange(history_key, -10, -1) 
    for item in raw_history:
        msg = json.loads(item)
        # Groq uses 'assistant' instead of 'model'
        role = "assistant" if msg['role'] == "model" else "user"
        messages.append({"role": role, "content": msg['content']})

    # ADD CURRENT MESSAGE
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
        if "429" in str(e):
            return jsonify({"error": "GURU is busy. Try again in 60 seconds."}), 429
        return jsonify({"error": str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({"message": "Logged out"}))
    resp.set_cookie('auth_token', '', expires=0)
    return resp

if __name__ == '__main__':
    app.run(debug=True)