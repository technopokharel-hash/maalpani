from flask import Flask, request, jsonify
import google.generativeai as genai
import redis
import jwt
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv  # <--- NEW IMPORT

# Load environment variables from .env file (for local development)
load_dotenv()  # <--- NEW CALL

app = Flask(__name__)

# --- CONFIGURATION ---
# Now os.environ.get will pull from your .env file locally
# In production (Vercel), it will pull from the dashboard settings automatically
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET")

# Connect to Redis
# If KV_URL is set (Vercel), use it. Otherwise default to local.
kv_url = os.environ.get("KV_URL", "redis://localhost:6379")
kv_token = os.environ.get("KV_REST_API_TOKEN")

# Logic to handle Vercel KV (REST) vs Standard Redis (Local)
if kv_token and "vercel-storage" in kv_url:
    # If strictly using Vercel KV over HTTP (optional specific setup)
    # usually redis.from_url works for both if the connection string is standard
    r = redis.from_url(kv_url, decode_responses=True) # Vercel KV usually supports standard protocol
else:
    # Standard Redis connection
    r = redis.from_url(kv_url, decode_responses=True) # decode_responses=True handles bytes automatically

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- HELPERS ---
def get_user_from_token():
    token = request.headers.get('Authorization')
    if not token:
        return None
    try:
        # Remove 'Bearer ' prefix
        token = token.split(" ")[1] 
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return data['username']
    except:
        return None

SYSTEM_PROMPT = "You are a friendly, casual AI assistant. Keep responses concise, helpful, and conversational. Do not be overly formal."

# --- ROUTES ---

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if r.exists(f"user:{username}"):
        return jsonify({"error": "User already exists"}), 400

    hashed_pw = generate_password_hash(password)
    # Store user data
    r.hset(f"user:{username}", mapping={"password": hashed_pw})
    
    return jsonify({"message": "User created"}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user_data = r.hgetall(f"user:{username}")
    
    # Redis returns bytes, need to decode
    stored_pw = user_data.get(b'password').decode('utf-8') if user_data else None

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
    
    # 1. Fetch History
    history_key = f"chat:{username}"
    # Get last 10 items (5 turns)
    raw_history = r.lrange(history_key, -10, -1) 
    chat_history = []
    
    for item in raw_history:
        msg = json.loads(item)
        chat_history.append({"role": msg['role'], "parts": [msg['content']]})

    # 2. Add current user message to context locally for Gemini
    chat_session = model.start_chat(history=chat_history)
    
    try:
        # 3. Send to Gemini with System Prompt guidance
        response = chat_session.send_message(f"System: {SYSTEM_PROMPT}\nUser: {user_message}")
        ai_message = response.text
        
        # 4. Save to DB
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

# For Vercel Serverless
app.debug = True