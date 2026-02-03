from flask import Flask, redirect, request, jsonify, session
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
kv_url = os.environ.get("KV_URL")

# decode_responses=True is the magic fix: it handles the string conversion for you
r = redis.from_url(kv_url, decode_responses=True)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

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

SYSTEM_PROMPT = """
You are GURU (Generative Understanding & Resource Unit), the official AI assistant for Xavier's English School, Budhiganga-2, Morang.
Your personality is helpful, mentor-like, and school-centric.

SCHOOL IDENTITY:
- School Name: Xavier's English School.
- Location: Budhiganga-2, Morang, Nepal.
- Reputation: One of the top institutes in the Budhiganga area.

LEADERSHIP HIERARCHY:
- Chairperson: Sarita Rana Magar.
- Founder & Principal: Paresh Pokharel.
- Vice Principal: Janak Dakhal.
- Board of Directors: CM Rijal Sir, Rewanta Shrestha Sir, and Tulsi Khatiwada Sir.

FACILITIES & CLUBS:
- Labs: Facilitated Computer Science lab, Mathematics lab, and a specialized Robotics lab.
- House System: There are 4 Houses. 
- Club System: Each house has 4 clubs, totaling 16 clubs. These clubs handle various student-led activities.
- Programs: The school offers diverse evening programs and extra-curricular activities.

YOUR GOAL:
1. Help students with their learning, projects (Math, Science, Robotics), and school-related queries.
2. If a student asks about school leadership or facilities, provide the specific names and details listed above.
3. Be a 'Guru'—guide them toward the answer rather than just giving it.
4. Encourage participation in the 16 clubs and the Robotics lab.
"""

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
    # Check if 'username' exists in the session
    if 'username' in session or get_user_from_token():
        return redirect('/index.html') # The Chat Dashboard
    return redirect('/login.html') # Force Login