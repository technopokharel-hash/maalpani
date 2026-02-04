import os, json, jwt, sys
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# --- VERCEL PATH FIX ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from school_data import get_guru_prompt
except ImportError:
    # Try alternate package path
    try:
        from api.school_data import get_guru_prompt
    except:
        def get_guru_prompt(): return "You are GURU, a helpful school assistant."

# --- INITIALIZE ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

MODEL_NAME = 'llama-3.3-70b-versatile'
JWT_SECRET = os.environ.get("JWT_SECRET", "xavier_guru_2026_secret")

# Globals for lazy loading
_client = None
_r = None

def get_services():
    """Wakes up Groq and Redis only when a request actually arrives."""
    global _client, _r
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ.get("GROQ_API_KEY")
        )
    if _r is None:
        import redis
        _r = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
    return _client, _r

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online", "ready": True}), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    client, r = get_services()
    # ... rest of your chat logic using 'client' and 'r'
    return jsonify({"reply": "GURU is connected!"})

# Ensure your signup/login routes also use get_services() to get the 'r' client
handler = app