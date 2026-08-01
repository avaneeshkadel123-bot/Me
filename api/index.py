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
        # Stat-appropriate fallback schools
        if gpa >= 3.7:
            fb_reach = ["Georgetown University", "University of Michigan", "NYU"]
            fb_target = ["Fordham University", "Tulane University", "University of Vermont"]
            fb_safety = ["Rutgers University", "University of Massachusetts Amherst", "Arizona State University"]
        elif gpa >= 3.2:
            fb_reach = ["University of Oregon", "Drexel University", "University of Denver"]
            fb_target = ["Pace University", "Quinnipiac University", "University of Montana"]
            fb_safety = ["SUNY Albany", "Northern Arizona University", "Western Michigan University"]
        elif gpa >= 2.5:
            fb_reach = ["University of New Mexico", "Eastern Michigan University", "University of Southern Maine"]
            fb_target = ["Western Kentucky University", "Murray State University", "Fitchburg State University"]
            fb_safety = ["Southern New Hampshire University", "Post University", "Granite State College"]
        else:
            fb_reach = ["Western New England University", "Limestone University", "Alcorn State University"]
            fb_target = ["Southern New Hampshire University", "Post University", "National University"]
            fb_safety = ["Community College options", "Excelsior University", "Western Governors University"]
        return jsonify({
            "success": True,
            "reach": fb_reach,
            "target": fb_target,
            "safety": fb_safety,
            "chances_summary": f"With a {gpa} GPA and {aps} AP/IB courses, your profile targets schools matched to your academic level. Connect a Groq API key for a fully personalized AI assessment.",
            "target_college_eval": f"Based on a {gpa} GPA, your chances at {target_college} depend heavily on their median admitted GPA. Connect a Groq API key for a detailed evaluation." if target_college else "",
            "growth_tips": [
                "Focus on raising your GPA — even a 0.2 point increase opens significantly more doors.",
                "Strengthen your personal statement to highlight unique experiences and growth.",
                "Pursue meaningful extracurriculars that show leadership and long-term commitment."
            ]
        }), 200

    # Build stat-aware tier guidance so the LLM picks schools that actually match the numbers
    if gpa >= 3.9:
        gpa_tier = "elite (top 1-5% of applicants)"
        reach_guidance = "Reach = Ivy League, MIT, Stanford, Caltech, Duke, Johns Hopkins"
        target_guidance = "Target = top 20-35 schools like UCLA, USC, NYU, Georgetown, UMich, UVA"
        safety_guidance = "Safety = solid state flagships like Penn State, University of Maryland, Pitt"
    elif gpa >= 3.6:
        gpa_tier = "strong (top 10-20% of applicants)"
        reach_guidance = "Reach = top 25 schools like Georgetown, UMich, UVA, UCLA, NYU"
        target_guidance = "Target = schools ranked 30-60 like Fordham, Tulane, University of Vermont, Lehigh"
        safety_guidance = "Safety = state schools like Rutgers, UMass Amherst, Arizona State, Temple"
    elif gpa >= 3.2:
        gpa_tier = "average (middle 40% of applicants)"
        reach_guidance = "Reach = schools ranked 50-80 like University of Oregon, Drexel, University of Denver"
        target_guidance = "Target = schools ranked 80-150 like University of Montana, Pace University, Quinnipiac"
        safety_guidance = "Safety = open-enrollment or high-acceptance schools like SUNY schools, Northern Arizona, Western Michigan"
    elif gpa >= 2.5:
        gpa_tier = "below average"
        reach_guidance = "Reach = schools with 50-70% acceptance like University of New Mexico, Eastern Michigan"
        target_guidance = "Target = schools with 70-85% acceptance like Western Kentucky, Murray State, Fitchburg State"
        safety_guidance = "Safety = high-acceptance schools (85-100%) like Southern New Hampshire, Strayer, community colleges"
    else:
        gpa_tier = "very low — most 4-year universities will be extremely difficult"
        reach_guidance = "Reach = schools with 60-80% acceptance like Western New England University, Limestone University"
        target_guidance = "Target = schools with 80-95% acceptance like Southern New Hampshire University, Post University"
        safety_guidance = "Safety = open-enrollment institutions and community colleges with near 100% acceptance"

    # Build the prompt with all available fields
    test_scores_line = ""
    if sat:
        test_scores_line += f"- SAT Score: {sat}\n"
    if act:
        test_scores_line += f"- ACT Score: {act}\n"
    weighted_line = f"- Weighted GPA: {weighted_gpa}/5.0\n" if weighted_gpa else ""
    target_line = f"- Target University: {target_college}\n" if target_college else ""

    prompt = (
        f"You are a brutally honest US college admissions counselor with deep knowledge of actual admission statistics.\n"
        f"You MUST match schools to the applicant's real stats. Do NOT recommend elite or selective schools if stats are weak.\n\n"
        f"APPLICANT STATS:\n"
        f"- Unweighted GPA: {gpa}/4.0 — this is {gpa_tier}\n"
        f"{weighted_line}"
        f"{test_scores_line}"
        f"- AP/IB/Honors Courses: {aps}\n"
        f"- Extracurricular Level: {ec_level}\n"
        f"- Target Major: {major}\n"
        f"{target_line}\n"
        f"CRITICAL RULES — follow these exactly:\n"
        f"- {reach_guidance}\n"
        f"- {target_guidance}\n"
        f"- {safety_guidance}\n"
        f"- NEVER put a school in Reach if the applicant has near-zero chance (below 5%). Those are impossible, not reaches.\n"
        f"- NEVER list MIT, Stanford, Harvard, Yale, Princeton, Columbia, Penn, Brown, Dartmouth, Cornell, or Duke "
        f"as Reach unless GPA is 3.7+ AND SAT is 1400+ or ACT is 32+.\n"
        f"- NEVER list University of Michigan, UCLA, UC Berkeley, Georgetown, NYU, or UVA as Target "
        f"unless GPA is 3.5+ AND test scores are at least SAT 1200 or ACT 26.\n"
        f"- Schools must be REAL US universities that actually exist.\n"
        f"- Be realistic and honest — a student with a {gpa} GPA cannot realistically target top-20 schools.\n\n"
        f"Return a JSON object with these exact keys:\n"
        f"1. 'reach': Array of exactly 3 university name strings that are genuinely reachable but unlikely given the stats\n"
        f"2. 'target': Array of exactly 3 university name strings where admission is realistically possible\n"
        f"3. 'safety': Array of exactly 3 university name strings where admission is very likely\n"
        f"4. 'chances_summary': 2 honest sentences assessing this applicant's real competitiveness based on their actual numbers\n"
        f"5. 'growth_tips': Array of exactly 3 specific actionable tips to improve their chances\n"
        f"6. 'target_college_eval': If a specific target university was given, give an honest 1-2 sentence assessment of their real odds there based on the school's actual median stats. Otherwise empty string.\n"
        f"Output ONLY valid JSON. Every array value must be a plain string."
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
            messages=[{"role": "system", "content": "You are a JSON-only response engine that strictly follows admissions statistics. Every array value must be a plain string, never an object. Never recommend schools the applicant has no realistic chance at."},
                      {"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
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
    
