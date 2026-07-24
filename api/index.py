import os
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Dynamically resolve absolute path to templates folder from api/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'templates'))

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Initialize Groq Engine
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Supabase Configurations
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

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

@app.route('/api/session/start', methods=['POST'])
def start_session():
    data = request.get_json() or {}
    track = data.get('track', 'General Corporate Interview')
    is_college = "college" in track.lower() or "admission" in track.lower()

    if not groq_client:
        initial_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        return jsonify({
            "success": True,
            "track": track,
            "current_question": initial_question,
            "history": [
                {"role": "user", "content": f"Initialize simulation environment for track: {track}."},
                {"role": "assistant", "content": initial_question}
            ]
        }), 200

    system_instruction = (
        "You are an elite US University Admissions Officer. Generate exactly ONE unique, challenging, "
        "and highly realistic initial opening interview question designed for an elite college applicant. "
        "Focus on themes of holistic character, community contribution, unique background, or personal growth. "
        "Do not output greetings, prefaces, or extra text. Output only the single question."
    ) if is_college else (
        "You are a principal corporate recruiter managing high-stakes behavioral screening loops in the US market. "
        "Generate exactly ONE unique, realistic, and highly professional initial interview question targeting "
        "a candidate's behavioral history. Do not output greetings, prefaces, or extra text. Output only the single question."
    )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_instruction}],
            temperature=0.85,
            max_tokens=150
        )
        initial_question = completion.choices[0].message.content.strip()
    except Exception:
        initial_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        
    return jsonify({
        "success": True,
        "track": track,
        "current_question": initial_question,
        "history": [
            {"role": "user", "content": f"Initialize simulation environment for track: {track}."},
            {"role": "assistant", "content": initial_question}
        ]
    }), 200

@app.route('/api/session/respond', methods=['POST'])
def process_response():
    data = request.get_json() or {}
    transcript = data.get('transcript', '')
    history = data.get('history', [])
    track = data.get('track', 'General Corporate Interview')
    is_college = "college" in track.lower() or "admission" in track.lower()
    
    cleaned_transcript = transcript.strip()
    if not cleaned_transcript:
        return jsonify({"success": False, "error": "No transcript provided."}), 400
        
    if not history or history[-1].get('content') != cleaned_transcript:
        history.append({"role": "user", "content": cleaned_transcript})
    
    if not groq_client:
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[Fallback mode] {fallback_question}"
        history.append({"role": "assistant", "content": next_question})
        return jsonify({"success": True, "next_question": next_question, "history": history}), 200

    context_guideline = (
        "You are an elite US University Admissions Officer. Review the conversation history. "
        "Ask exactly ONE incisive follow-up question. Output only the question."
    ) if is_college else (
        "You are an expert technical recruiter. Review the conversation history. "
        "Ask exactly ONE professional follow-up question. Output only the question."
    )

    messages = [{"role": "system", "content": context_guideline}]
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        next_question = completion.choices[0].message.content.strip()
    except Exception:
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[Fallback Prompt] {fallback_question}"

    history.append({"role": "assistant", "content": next_question})
    return jsonify({"success": True, "next_question": next_question, "history": history}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
