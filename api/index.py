import os, sys, json, jwt
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Path fix for Vercel
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "Superbaby")
MODEL_NAME = "gpt-4o-mini"

# Lazy Service Singletons
_openai_client = None
_redis_client = None

def get_services():
    global _openai_client, _redis_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(os.environ.get("KV_URL"), decode_responses=True)
    return _openai_client, _redis_client

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # 1. Auth Check (Same as Gemini version)
        token = request.cookies.get('token')
        if not token: return jsonify({"error": "Unauthorized"}), 401
        username = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])['username']

        # 2. Lazy Load Services
        ai, r = get_services()
        
        data = request.json
        user_message = data.get("message")
        history_key = f"chat:{username}"

        # 3. Handle History (Same procedure as Gemini)
        messages = [{"role": "system", "content": "You are GURU, a helpful assistant."}]
        try:
            history = r.lrange(history_key, -5, -1)
            for h in history:
                item = json.loads(h)
                messages.append({"role": item['role'], "content": item['content']})
        except: pass

        messages.append({"role": "user", "content": user_message})

        # 4. OpenAI Call
        response = ai.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        reply = response.choices[0].message.content

        # 5. Save Procedure
        r.rpush(history_key, json.dumps({"role": "user", "content": user_message}))
        r.rpush(history_key, json.dumps({"role": "assistant", "content": reply}))
        r.ltrim(history_key, -20, -1)

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

handler = app