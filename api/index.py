import os, json, jwt, sys
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --- 1. ABSOLUTE PATH INJECTION ---
# This fixes the 'ImportError' seen in your screenshots by telling Python exactly where to look.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

try:
    from school_data import get_guru_prompt
except ImportError:
    # Fallback if the file is moved or renamed during deployment
    def get_guru_prompt(): return "You are GURU, a helpful school assistant."

# --- 2. APP INITIALIZATION ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuration from your Vercel Dashboard
JWT_SECRET = os.environ.get("JWT_SECRET") 
MODEL_NAME = "gpt-4o-mini"

# --- 3. LAZY SERVICE HANDLER ---
# We keep these 'None' at the top to prevent a crash if the network is slow during startup.
_client = None
_redis = None

def get_services():
    """Initializes AI and Database only when a request actually arrives."""
    global _client, _redis
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if _redis is None:
        import redis
        _redis = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
    return _client, _redis

# --- 4. ROUTES ---

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # Check authentication first
        token = request.cookies.get('token')
        if not token: return jsonify({"error": "Unauthorized"}), 401
        
        username = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])['username']
        
        # Wake up services
        ai, r = get_services()
        
        user_message = request.json.get('message')
        history_key = f"chat:{username}"
        
        # Build prompt
        messages = [{"role": "system", "content": get_guru_prompt()}]
        
        # Safe history retrieval
        try:
            history = r.lrange(history_key, -5, -1)
            for m in history:
                msg = json.loads(m)
                messages.append({"role": msg['role'], "content": msg['content']})
        except: pass

        messages.append({"role": "user", "content": user_message})

        # OpenAI Call
        completion = ai.chat.completions.create(model=MODEL_NAME, messages=messages)
        reply = completion.choices[0].message.content

        # Save to Redis
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "assistant", "content": reply}))
        r.ltrim(history_key, -20, -1)

        return jsonify({"reply": reply})

    except Exception as e:
        # This will show up in your Vercel 'Functions' logs
        print(f"Chat Error: {str(e)}")
        return jsonify({"error": "Server is waking up, please try again."}), 503

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online", "secret_check": JWT_SECRET is not None}), 200

# Vercel entry point
handler = app