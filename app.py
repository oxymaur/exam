#!/usr/bin/env python3
import os
import json
import random
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime

# -- CONFIG ----------------------------------------------------------------
EA_QUESTIONS_FILE = "questions_db.json"   # Original EA quiz
AFM_QUESTIONS_FILE = "afm_questions.json" # New AFM quiz
SCORES_FILE = "scores.json"
NUM_QUESTIONS = 20  # how many questions to present
SECRET_KEY = os.urandom(24)  # for session encryption

app = Flask(__name__)
app.secret_key = SECRET_KEY

# -- LOAD / SAVE FUNCTIONS ------------------------------------------------

def load_subject_questions(subject_choice):
    """
    Load questions from the appropriate JSON file, based on 'subject_choice'.
    subject_choice will be 'ea' or 'afm'.
    """
    if subject_choice == "afm":
        filename = AFM_QUESTIONS_FILE
    else:
        # default = EA
        filename = EA_QUESTIONS_FILE

    with open(filename, "r", encoding="utf-8") as f:
        all_qs = json.load(f)

    return all_qs

def load_scores():
    """Load existing scores from SCORES_FILE."""
    if not os.path.exists(SCORES_FILE):
        return []
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_scores(scores_list):
    """Save updated scores list to SCORES_FILE."""
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores_list, f, indent=2)

# -- ROUTES ----------------------------------------------------------------

@app.route("/")
def index():
    """
    Landing page: 
    1) User enters name 
    2) Selects subject (EA or AFM)
    3) Sees top 5 scores from any quiz attempts
    """
    scores_data = load_scores()
    # Sort descending by score
    scores_data.sort(key=lambda x: x["score"], reverse=True)
    top_5 = scores_data[:5]

    return render_template("welcome.html", top_scores=top_5)


@app.route("/start_quiz", methods=["POST"])
def start_quiz():
    """Initialize the quiz session after user enters name & subject."""
    username = request.form.get("username", "").strip()
    subject = request.form.get("subject", "ea")  # "ea" or "afm"

    if not username:
        flash("Please enter your name.")
        return redirect(url_for("index"))

    # Store user info in session
    session["username"] = username
    session["subject"] = subject

    # Load all questions for chosen subject
    all_questions = load_subject_questions(subject)

    # Select random subset if more questions than NUM_QUESTIONS
    if len(all_questions) <= NUM_QUESTIONS:
        selected = all_questions
    else:
        selected = random.sample(all_questions, NUM_QUESTIONS)

    random.shuffle(selected)

    session["questions"] = selected
    session["current_index"] = 0
    session["score"] = 0

    return redirect(url_for("quiz_question"))


@app.route("/quiz", methods=["GET", "POST"])
def quiz_question():
    """
    Show the current question, handle answer submission, 
    and show immediate feedback (Correct/Incorrect + explanation).
    """
    if "questions" not in session or "current_index" not in session:
        flash("No quiz session found. Please start again.")
        return redirect(url_for("index"))

    questions = session["questions"]
    current_index = session["current_index"]
    score = session["score"]

    # If we've reached or passed final question
    if current_index >= len(questions):
        return redirect(url_for("quiz_results"))

    question_data = questions[current_index]

    # We'll store feedback to show user whether they're correct or not
    feedback = {
        "submitted": False,
        "is_correct": False,
        "explanation": ""
    }

    if request.method == "POST":
        # Distinguish between "submit_answer" and "next_question"
        if "submit_answer" in request.form:
            # The user clicked "Submit Answer"
            correct_set = set(question_data["correct_answers"])
            user_answers = request.form.getlist("selected_options")
            user_set = set(ans.strip().lower() for ans in user_answers)

            feedback["submitted"] = True
            feedback["is_correct"] = (user_set == correct_set)
            feedback["explanation"] = question_data.get("explanation", "No explanation provided.")

            if feedback["is_correct"]:
                score += 1
                session["score"] = score

            # We do NOT increment current_index yet; user must click "Next"
        elif "next_question" in request.form:
            # The user clicked "Next Question"
            current_index += 1
            session["current_index"] = current_index
            return redirect(url_for("quiz_question"))

    return render_template(
        "quiz.html",
        question=question_data,
        index=current_index + 1,
        total=len(questions),
        score=score,
        feedback=feedback
    )


@app.route("/results")
def quiz_results():
    """Show final results and store them in scores.json."""
    if "username" not in session:
        flash("No username in session. Start again.")
        return redirect(url_for("index"))

    username = session["username"]
    score = session.get("score", 0)
    questions = session.get("questions", [])
    total = len(questions) if questions else 1
    percent = (score / total * 100) if total else 0

    # Save to scores.json
    scores_data = load_scores()
    new_entry = {
        "name": username,
        "score": percent,
        "timestamp": datetime.now().isoformat()
    }
    scores_data.append(new_entry)
    save_scores(scores_data)

    # best score so far
    best_score = max(item["score"] for item in scores_data) if scores_data else percent

    # Clear session so user can start again if desired
    session.clear()

    return render_template("results.html", 
                           username=username, 
                           score=score,
                           total=total, 
                           percent=percent, 
                           best_score=best_score)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
