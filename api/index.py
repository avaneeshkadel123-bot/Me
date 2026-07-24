import os
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Dynamically locate the templates directory relative to api/index.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, '..', 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Initialize Groq Engine
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Supabase Configurations
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Datasets
FALLBACK_CORPORATE_QUESTIONS = [
    "Thank you for joining this career simulation panel. US professional environments place a heavy emphasis on behavioral indicators. Let's begin by discussing a time when you had to manage competing deliverables or project constraints. What specific actions did you implement to ensure success?",
    "Could you walk me through a technical initiative you spearheaded where you encountered severe ambiguity? How did you define the project parameters and align your team?",
    "Describe a situation where you had a significant disagreement with a colleague or stakeholder on an architectural choice. How did you navigate the conflict to deliver results?"
]

FALLBACK_COLLEGE_QUESTIONS = [
    "Welcome to your admissions assessment simulation. US higher education institutions prioritize unique community contributions and holistic character. Could you describe a significant extracurricular initiative or academic challenge where you took the lead, and detail the personal growth you experienced as a result?",
    "Elite academic environments thrive on diverse perspectives. What unique facet of your background or personal journey will allow you to enrich our campus culture?",
    "Tell me about a time you failed to achieve a major personal or academic goal. How did you process that setback, and what structural changes did you make to your methodology moving forward?"
]

@app.route('/')
def home():
    """Renders the single-page glassmorphic user workspace dashboard."""
    return render_template(
        'index.html',
        supabase_url=SUPABASE_URL,
        supabase_anon_key=SUPABASE_ANON_KEY
    )

@app.route('/api/health', methods=['GET'])
def health_check():
    """Validates cloud service integrity and connection dependencies."""
    return jsonify({
        "status": "operational",
        "environment": "US-Standard-2026",
        "groq_connected": groq_client is not None,
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    }), 200

@app.route('/api/auth/config', methods=['GET'])
def auth_config():
    """Provides client-side authentication configuration parameters."""
    return jsonify({
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
