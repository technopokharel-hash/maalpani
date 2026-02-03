from flask import Flask, request, jsonify
import google.generativeai as genai
import redis
import jwt
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")

# Connect to Redis
# Using your provided Cloud Redis URL. 
# Added rediss:// (double 's') because most cloud providers require SSL/TLS.
kv_url = os.environ.get("KV_URL", "rediss://default:EDaOZaJ5tZ03vFs3fwZUwBjQGXHTP230@redis-19024.c239.us-east-1-2.ec2.cloud.redislabs.com:19024")

# decode_responses=True is the magic fix: it handles the string conversion for you
r = redis.from_url(kv_url, decode_responses=True)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- HELPERS ---
def get_user_from_token():
    token = request.headers.get('Authorization')
    if not token or "Bearer " not in token:
        return None
    try:
        token = token.split(" ")[1] 
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except:
        return None

SYSTEM_PROMPT = "You are a friendly, casual AI assistant. Keep responses concise and conversational."

# --- ROUTES ---

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if r.exists(f"user:{username}"):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = generate_password_hash(password)
    r.hset(f"user:{username}", mapping={"password": hashed_pw})
    return jsonify({"message": "User created"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Fetch user data from Redis
    user_data = r.hgetall(f"user:{username}")
    
    # FIX: No .decode() needed because of decode_responses=True
    stored_pw = user_data.get('password') 

    if stored_pw and check_password_hash(stored_pw, password):
        token = jwt.encode({
            'username': username,
            'exp': datetime.utcnow() + timedelta(days=7)
        }, JWT_SECRET, algorithm="HS256")
        return jsonify({"token": token, "username": username})
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/chat', methods=['POST'])
def chat():
    username = get_user_from_token()
    if not username:
        return jsonify({"error": "Unauthorized"}), 401

    user_message = request.json.get('message')
    history_key = f"chat:{username}"
    
    raw_history = r.lrange(history_key, -10, -1) 
    chat_history = []
    
    for item in raw_history:
        msg = json.loads(item)
        chat_history.append({"role": msg['role'], "parts": [msg['content']]})

    chat_session = model.start_chat(history=chat_history)
    
    try:
        response = chat_session.send_message(f"System: {SYSTEM_PROMPT}\nUser: {user_message}")
        ai_message = response.text
        
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "model", "content": ai_message}))
        
        return jsonify({"reply": ai_message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    username = get_user_from_token()
    if username:
        r.delete(f"chat:{username}")
        return jsonify({"message": "History cleared"})
    return jsonify({"error": "Unauthorized"}), 401

@app.route('/')
def home():
    return "Backend is running! Visit /login.html to start."