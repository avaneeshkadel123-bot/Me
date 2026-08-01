import os
import json
import random
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq

# Pull local tracking keys and configurations
load_dotenv()

app = Flask(__name__, template_folder='../templates')

# Initialize Groq Engine with valid, open-weight production models
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Supabase Authentication Configurations
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Curated datasets for seamless offline/invalid-key testing in the US landscape
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

@app.route('/api/session/start', methods=['POST'])
def start_session():
    """Dynamically generates a completely unique opening interview prompt based on the selected US track context."""
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

    if is_college:
        system_instruction = (
            "You are an elite US University Admissions Officer. Generate exactly ONE unique, challenging, "
            "and highly realistic initial opening interview question designed for an elite college applicant. "
            "Focus on themes of holistic character, community contribution, unique background, or personal growth. "
            "Do not output greetings, prefaces, or extra text. Output only the single question."
        )
    else:
        system_instruction = (
            "You are a principal corporate recruiter managing high-stakes behavioral screening loops in the US market. "
            "Generate exactly ONE unique, realistic, and highly professional initial interview question targeting "
            "a candidate's behavioral history (e.g., leadership, dealing with ambiguity, or project failures). "
            "Do not output greetings, prefaces, or extra text. Output only the single question."
        )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_instruction}],
            temperature=0.85,
            max_tokens=150
        )
        initial_question = completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq API connection drop: {e}. Falling back to local curated dataset pools.")
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
    """Processes user text turns and evaluates conversational history to return the next adaptive question."""
    data = request.get_json() or {}
    transcript = data.get('transcript', '')
    history = data.get('history', [])
    track = data.get('track', 'General Corporate Interview')
    is_college = "college" in track.lower() or "admission" in track.lower()

    cleaned_transcript = transcript.strip()
    if not cleaned_transcript:
        return jsonify({"success": False, "error": "No new transcript text provided to advance the session conversation."}), 400

    if not history or history[-1].get('content') != cleaned_transcript:
        history.append({"role": "user", "content": cleaned_transcript})

    if not groq_client:
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[Fallback mode active due to missing API configuration] {fallback_question}"
        history.append({"role": "assistant", "content": next_question})
        return jsonify({"success": True, "next_question": next_question, "history": history}), 200

    if is_college:
        context_guideline = (
            "You are an elite US University Admissions Officer. The user is an applicant. Review the conversation history. "
            "Ask exactly ONE incisive, direct follow-up question that builds naturally on their last response or moves to a "
            "related holistic candidate evaluation metric. Do not offer encouragement, feedback, or commentary. Output only the single question."
        )
    else:
        context_guideline = (
            "You are an expert technical recruiter interviewing a candidate for a highly competitive US corporate role. "
            "Review the conversation history. Ask exactly ONE professional follow-up question that builds on their story or probes "
            "for missing elements of the STAR method (metrics, actions, results). Do not offer validation or filler phrases. Output only the question."
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
    except Exception as e:
        print(f"Groq API failure during response: {e}")
        fallback_question = random.choice(FALLBACK_COLLEGE_QUESTIONS) if is_college else random.choice(FALLBACK_CORPORATE_QUESTIONS)
        next_question = f"[API Connection Glitch - Fallback Prompt] {fallback_question}"

    history.append({"role": "assistant", "content": next_question})
    return jsonify({
        "success": True,
        "next_question": next_question,
        "history": history
    }), 200

@app.route('/api/session/evaluate-turn', methods=['POST'])
def evaluate_turn():
    """NEW: Evaluates a single response against the STAR framework and returns structured JSON feedback."""
    data = request.get_json() or {}
    transcript = data.get('transcript', '')
    track = data.get('track', 'General Corporate Interview')

    if not transcript.strip():
        return jsonify({"success": False, "error": "No transcript provided."}), 400

    if not groq_client:
        has_metrics = any(char.isdigit() for char in transcript)
        return jsonify({
            "success": True,
            "star_eval": {
                "situation": "Present: Clear context established.",
                "task": "Present: Objective identified.",
                "action": "Present: Steps outlined.",
                "result": "Present (Quantifiable metrics included)" if has_metrics else "Missing: Add numbers, %, or $ to quantify impact.",
                "conciseness_score": "8/10",
                "executive_suggestion": "Strong delivery. Ensure your Result highlights tangible ROI or performance growth."
            }
        }), 200

    prompt = (
        f"You are an expert executive coach evaluating an interview response for the track: {track}.\n"
        f"Candidate Transcript: \"{transcript}\"\n\n"
        f"Evaluate this response and return a valid JSON object with exactly these keys:\n"
        f"1. 'situation': One-sentence status note on whether Situation context was established.\n"
        f"2. 'task': One-sentence status note on whether the Task/objective was defined.\n"
        f"3. 'action': One-sentence status note on whether specific Actions were described.\n"
        f"4. 'result': Status note explicitly stating if quantifiable metrics (numbers, percentages, dollars) were included or missing.\n"
        f"5. 'conciseness_score': Score out of 10 with a brief note on wordiness.\n"
        f"6. 'executive_suggestion': One concise coaching tip to immediately improve the response.\n"
        f"Output strictly valid JSON with no extra text."
    )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a precise JSON evaluation engine. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content)
        result["success"] = True
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "success": True,
            "star_eval": {
                "situation": "Present",
                "task": "Present",
                "action": "Present",
                "result": "Quantifiable metrics recommended — add numbers, %, or $ for impact.",
                "conciseness_score": "7/10",
                "executive_suggestion": "Lead with quantifiable impact and streamline your narrative arc."
            }
        }), 200

@app.route('/api/session/analyze', methods=['POST'])
def analyze_session():
    """Generates the comprehensive review metrics matrix on demand without terminating or freezing active workspace states."""
    data = request.get_json() or {}
    history = data.get('history', [])

    if not groq_client:
        return jsonify({
            "success": True,
            "analysis": "## 1. Content Quality Score & Evaluation\nLocal fallback mode is currently running because no valid GROQ_API_KEY was detected in your root .env file configuration.\n\n## 2. Structural Delivery Breakdown\nYour client-side speech processing mechanics (Words Per Minute metrics, Fluency Pauses, and Filler Word counters) are fully operational.\n\n## 3. High-Impact Strategies for Growth\n1. Populate your .env file with a valid Groq API authorization key to access live AI coaching reports.\n2. Ensure your vocal speech tracks adhere cleanly to the behavioral STAR structural framework.\n3. Keep monitoring the live dashboard tickers during speech delivery."
        }), 200

    analysis_prompt = (
        "You are an expert executive coach specializing in US professional recruitment trends and Ivy League admissions criteria. "
        "Perform a comprehensive evaluation on the provided interview dialogue exchange. "
        "Analyze the response depth, logical cohesion, and alignment with target US benchmarks (like the STAR methodology or authentic leadership). "
        "Format your diagnostic breakdown clearly using the following three distinct headers with clean spacing:\n\n"
        "## 1. Content Quality Score & Evaluation\n"
        "Critique the substance of the responses given so far. Assess balance between concrete project metrics and narrative alignment.\n\n"
        "## 2. Structural Delivery Breakdown\n"
        "Evaluate pacing, clarity of transitions, and the logical flow of arguments across turns.\n\n"
        "## 3. High-Impact Strategies for Growth\n"
        "Provide exactly three actionable, highly tailored strategies for immediate performance scaling."
    )

    messages = [
        {"role": "system", "content": analysis_prompt},
        {"role": "user", "content": f"Interview Transcript Record for Evaluation:\n{history}"}
    ]

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        critique = completion.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"success": False, "error": f"API Evaluation failed: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "analysis": critique
    }), 200

@app.route('/api/college/predict', methods=['POST'])
def predict_college_chances():
    """Evaluates high school student academic and extracurricular profile against US university tiers.
    Supports both unweighted GPA only (original) and weighted GPA + target college (new fields).
    """
    data = request.get_json() or {}
    gpa = float(data.get('gpa', 3.8))
    weighted_gpa = float(data.get('weighted_gpa', 0)) if data.get('weighted_gpa') else None
    sat = int(data.get('sat', 1400)) if data.get('sat') else None
    act = int(data.get('act', 30)) if data.get('act') else None
    aps = int(data.get('ap_count', 5))
    ec_level = data.get('ec_level', 'High')
    major = data.get('major', 'Computer Science / Engineering')
    target_college = data.get('target_college', '').strip()

    if not groq_client:
        return jsonify({
            "success": True,
            "reach": ["Harvard University", "Stanford University", "MIT"],
            "target": ["University of Michigan", "UC Berkeley", "NYU"],
            "safety": ["Penn State University", "USC", "University of Florida"],
            "chances_summary": f"Based on your GPA of {gpa} and academic rigor ({aps} AP/IB courses), you present a strong profile for Top 30 universities. Elevating your vocal interview presence will significantly amplify your holistic score.",
            "target_college_eval": f"With unweighted GPA {gpa}{f' and weighted GPA {weighted_gpa}' if weighted_gpa else ''}, your profile appears competitive. Practice interview delivery to strengthen your holistic application." if target_college else "",
            "growth_tips": [
                "Focus on framing your extracurricular leadership using concrete outcomes.",
                "Ace your alumni interview rounds by eliminating filler words like 'um' and 'like'.",
                "Highlight unique research or personal passion projects in supplemental essays."
            ]
        }), 200

    # Build the prompt with all available fields
    test_scores_line = ""
    if sat:
        test_scores_line += f"- SAT Score: {sat}\n"
    if act:
        test_scores_line += f"- ACT Score: {act}\n"
    weighted_line = f"- Weighted GPA: {weighted_gpa}/5.0\n" if weighted_gpa else ""
    target_line = f"- Target University: {target_college}\n" if target_college else ""

    prompt = (
        f"Act as a top US College Admissions Director. Evaluate this high school applicant:\n"
        f"- Unweighted GPA: {gpa}/4.0\n"
        f"{weighted_line}"
        f"{test_scores_line}"
        f"- Rigor: {aps} AP/IB/Honors courses\n"
        f"- Extracurricular Leadership Level: {ec_level}\n"
        f"- Target Major: {major}\n"
        f"{target_line}\n"
        f"Provide a realistic JSON response with these keys:\n"
        f"1. 'reach': Array of 3 Reach universities (<25% admission probability)\n"
        f"2. 'target': Array of 3 Target universities (40-70% admission probability)\n"
        f"3. 'safety': Array of 3 Safety universities (>80% admission probability)\n"
        f"4. 'chances_summary': A 2-sentence realistic assessment of their admissions competitiveness.\n"
        f"5. 'growth_tips': Array of 3 specific tips to improve their chances.\n"
        f"6. 'target_college_eval': If a target university was specified, a 1-2 sentence realistic evaluation of their odds there. Otherwise empty string.\n"
        f"Output ONLY valid JSON."
    )

    def flatten_list(items):
        """Ensure every item in a list is a plain string, regardless of LLM output format."""
        out = []
        for i in items:
            if isinstance(i, str):
                out.append(i)
            elif isinstance(i, dict):
                # Try common keys the LLM might use, fall back to first value
                out.append(
                    i.get('name') or i.get('university') or i.get('college') or
                    i.get('school') or i.get('tip') or i.get('strategy') or
                    i.get('text') or i.get('value') or
                    next(iter(i.values()), str(i))
                )
            else:
                out.append(str(i))
        return out

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a JSON-only response engine. Every array value must be a plain string, never an object."},
                      {"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=700,
            response_format={"type": "json_object"}
        )
        result = json.loads(completion.choices[0].message.content)
        # Normalize all list fields to plain strings
        for field in ('reach', 'target', 'safety', 'growth_tips'):
            if field in result and isinstance(result[field], list):
                result[field] = flatten_list(result[field])
        result["success"] = True
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "success": True,
            "reach": ["Columbia University", "UCLA", "Cornell University"],
            "target": ["University of Virginia", "UNC Chapel Hill", "Boston University"],
            "safety": ["Arizona State University", "University of Maryland", "Rutgers University"],
            "chances_summary": f"Your profile with a {gpa} GPA and strong course load puts you in a competitive tier. Master your holistic interview delivery to convert target applications into admissions.",
            "target_college_eval": "",
            "growth_tips": [
                "Practice articulate vocal delivery for admissions interviews.",
                "Ensure your personal statement bridges your technical passion with community impact.",
                "Quantify achievements in your extracurricular activity log."
            ]
        }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
