import os, sys, json
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

# Absolute path fix for Vercel
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# Minimal API Setup
def get_ai_client():
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        client = get_ai_client()
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": data.get("message")}]
        )
        
        return jsonify({"reply": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Server handle for Vercel
handler = app