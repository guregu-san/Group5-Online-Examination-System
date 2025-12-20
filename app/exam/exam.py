import sqlite3
import json
from datetime import datetime

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash
)

from .form import ExamCreateForm


# Blueprint
examBp = Blueprint(
    "examBp",
    __name__,
    url_prefix="/exams",
    template_folder="templates"
)


# -----------------------------
# DB Helper
# -----------------------------
def get_db():
    conn = sqlite3.connect("oesDB.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# -----------------------------
# Helper Functions
# -----------------------------
def _parse_datetime(value):
    """Convert HTML datetime-local or ISO string → datetime object."""
    if isinstance(value, datetime):
        return value
    if value is None:
        return None

    # HTML datetime-local: 2025-01-01T10:30
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except:
        pass

    # ISO fallback
    try:
        return datetime.fromisoformat(value)
    except:
        return None


def _normalize_security_settings(security_settings):
    """Ensure security settings are stored as valid JSON."""
    if not security_settings:
        return json.dumps([])

    if isinstance(security_settings, (list, dict)):
        return json.dumps(security_settings)

    if isinstance(security_settings, str):
        try:
            return json.dumps(json.loads(security_settings))  # already JSON
        except:
            # convert CSV → JSON
            parts = [p.strip() for p in security_settings.split(",") if p.strip()]
            return json.dumps(parts)

    return json.dumps([])


# -----------------------------
# Create Exam (Internal Logic)
# -----------------------------
def _create_exam_in_db(course_code, instructor_email, title, opens_at, closes_at, security_settings):
    """Insert a new exam with full validation."""

    if not course_code or not instructor_email:
        return False, "course_code and instructor_email are required", 400

    opens_dt = _parse_datetime(opens_at)
    closes_dt = _parse_datetime(closes_at)

    if not opens_dt or not closes_dt:
        return False, "Invalid date/time format.", 400

    if closes_dt <= opens_dt:
        return False, "Closing time must be after opening time.", 400

    if closes_dt < datetime.now():
        return False, "Exam cannot close in the past.", 400

    conn = get_db()
    cur = conn.cursor()

    # Validate instructor by EMAIL ONLY (fix for ambiguous instructor names)
    cur.execute("SELECT email FROM instructors WHERE email = ?", (instructor_email,))
    if not cur.fetchone():
        conn.close()
        return False, "Instructor does not exist", 400

    # Validate course
    cur.execute("""
        SELECT course_code, instructor_email
        FROM courses
        WHERE course_code = ?
    """, (course_code,))
    course = cur.fetchone()

    if not course:
        conn.close()
        return False, "Course does not exist", 400

    # Ensure correct instructor
    if course["instructor_email"] != instructor_email:
        conn.close()
        return False, "Instructor is not assigned to this course", 400

    # Convert settings to JSON
    security_json = _normalize_security_settings(security_settings)

    # Create exam
    cur.execute("""
        INSERT INTO exams (
            course_code, instructor_email, title, security_settings,
            opens_at, closes_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        course_code,
        instructor_email,
        title or "Untitled Exam",
        security_json,
        opens_dt.strftime("%Y-%m-%dT%H:%M"),
        closes_dt.strftime("%Y-%m-%dT%H:%M"),
    ))

    exam_id = cur.lastrowid
    conn.commit()
    conn.close()

    return True, {"exam_id": exam_id}, 201


# -----------------------------
# Create Exam (UI)
# -----------------------------
@examBp.route("/create", methods=["GET", "POST"])
def create_exam_ui():
    form = ExamCreateForm()

    if form.validate_on_submit():
        course_code = form.course_code.data.strip()
        instructor_email = form.instructor_email.data.strip()
        title = form.title.data.strip()

        opens_at = form.opens_at.data
        closes_at = form.closes_at.data
        security_settings = form.security_settings.data or ""

        # Local validation
        if closes_at <= opens_at:
            flash("Closing time must be after opening time.", "danger")
            return render_template("exam_create.html", form=form)

        if closes_at < datetime.now():
            flash("Closing time cannot be in the past.", "danger")
            return render_template("exam_create.html", form=form)

        success, result, status = _create_exam_in_db(
            course_code, instructor_email, title,
            opens_at, closes_at, security_settings
        )

        if not success:
            flash(result, "danger")
        else:
            flash("Exam created successfully!", "success")
            return redirect(url_for("examBp.edit_exam_ui", exam_id=result["exam_id"]))

    return render_template("exam_create.html", form=form)


# -----------------------------
# Add Question UI
# -----------------------------
@examBp.route("/<int:exam_id>/questions/new", methods=["GET", "POST"])
def add_question_ui(exam_id):

    if request.method == "POST":
        q_type = request.form.get("question_type")
        question_text = request.form.get("question_text", "").strip()

        if not question_text:
            flash("Question text is required.", "danger")
            return redirect(request.url)

        options = []
        is_multiple_correct = False

        # ---------------- MCQ ----------------
        if q_type == "mcq":
            for i in range(1, 5):
                text = request.form.get(f"opt{i}", "").strip()
                if text:
                    is_correct = request.form.get(f"opt{i}_correct") == "on"
                    options.append({
                        "option_text": text,
                        "is_correct": is_correct
                    })

            if not options:
                flash("At least one option is required.", "danger")
                return redirect(request.url)

            correct_count = sum(1 for opt in options if opt["is_correct"])

            if correct_count == 0:
                flash("You must select exactly ONE correct answer.", "danger")
                return redirect(request.url)

            if correct_count > 1:
                flash("Only ONE correct answer is allowed for Multiple Choice questions.", "danger")
                return redirect(request.url)

            is_multiple_correct = False

        # ---------------- TRUE / FALSE ----------------
        elif q_type == "true_false":
            correct = request.form.get("tf_answer")

            if correct not in ["true", "false"]:
                flash("You must select the correct answer.", "danger")
                return redirect(request.url)

            options = [
                {"option_text": "True", "is_correct": correct == "true"},
                {"option_text": "False", "is_correct": correct == "false"},
            ]
            is_multiple_correct = False

        # ---------------- TEXT ANSWERS ----------------
        elif q_type in ["short", "numerical", "essay"]:
            answer = request.form.get("text_answer", "").strip()

            if not answer:
                flash("Expected answer is required.", "danger")
                return redirect(request.url)

            options = [{"option_text": answer, "is_correct": True}]
            is_multiple_correct = False

        else:
            flash("Invalid question type.", "danger")
            return redirect(request.url)

        # ---------------- DB ----------------
        conn = get_db()
        cur = conn.cursor()

        # Check exam exists
        cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
        if not cur.fetchone():
            conn.close()
            flash("Exam not found.", "danger")
            return redirect(url_for("examBp.create_exam_ui"))

        # Order index
        cur.execute("""
            SELECT COALESCE(MAX(order_index), 0)
            FROM questions
            WHERE exam_id = ?
        """, (exam_id,))
        order_index = cur.fetchone()[0] + 1

        # Insert question
        cur.execute("""
            INSERT INTO questions (exam_id, question_text, is_multiple_correct, points, order_index)
            VALUES (?, ?, ?, ?, ?)
        """, (
            exam_id,
            question_text,
            1 if is_multiple_correct else 0,
            1,
            order_index
        ))

        question_id = cur.lastrowid

        # Insert options
        for opt in options:
            cur.execute("""
                INSERT INTO options (question_id, option_text, is_correct)
                VALUES (?, ?, ?)
            """, (
                question_id,
                opt["option_text"],
                1 if opt["is_correct"] else 0
            ))

        conn.commit()
        conn.close()

        flash("Question added!", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    return render_template("add_question.html", exam_id=exam_id)

# -----------------------------
# Preview Exam
# -----------------------------
@examBp.route("/<int:exam_id>/preview", methods=["GET"])
def preview_exam_ui(exam_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT exam_id, title, opens_at, closes_at, security_settings
        FROM exams
        WHERE exam_id = ?
    """, (exam_id,))
    exam = cur.fetchone()

    if not exam:
        conn.close()
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    cur.execute("""
        SELECT order_index, question_text
        FROM questions
        WHERE exam_id = ?
        ORDER BY order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()

    conn.close()

    return render_template("exam_preview.html", exam=exam, questions=questions, exam_id=exam_id)


# -----------------------------
# JSON API CREATE EXAM
# -----------------------------
@examBp.route("", methods=["POST"])
def create_exam():
    data = request.get_json(silent=True) or {}

    success, result, status = _create_exam_in_db(
        data.get("course_code"),
        data.get("instructor_email"),
        data.get("title", "Untitled Exam"),
        data.get("opens_at"),
        data.get("closes_at"),
        data.get("security_settings", "")
    )

    if not success:
        return jsonify(error=result), status

    return jsonify(message="Exam created", exam_id=result["exam_id"]), status


# -----------------------------
# LIST EXAMS BY INSTRUCTOR
# -----------------------------
@examBp.route("/instructor/<path:email>", methods=["GET"])
def list_exams_by_instructor(email):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT exam_id, title, course_code, opens_at, closes_at,
               security_settings, created_at, updated_at
        FROM exams
        WHERE instructor_email = ?
        ORDER BY created_at DESC
    """, (email,))
    rows = cur.fetchall()

    conn.close()
    return jsonify([row_to_dict(r) for r in rows]), 200


# -----------------------------
# EDIT EXAM UI
# -----------------------------
@examBp.route("/<int:exam_id>/edit", methods=["GET"])
def edit_exam_ui(exam_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT exam_id, title, opens_at, closes_at, security_settings
        FROM exams
        WHERE exam_id = ?
    """, (exam_id,))
    exam = cur.fetchone()

    if not exam:
        conn.close()
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    cur.execute("""
        SELECT question_id, question_text, is_multiple_correct, order_index
        FROM questions
        WHERE exam_id = ?
        ORDER BY order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()

    conn.close()

    return render_template("exam_edit.html", exam=exam, questions=questions)


# -----------------------------
# SECURITY UI
# -----------------------------
@examBp.route("/<int:exam_id>/security", methods=["GET", "POST"])
def set_security_ui(exam_id):

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        shuffle = request.form.get("shuffle") == "on"
        disable_copy = request.form.get("disable_copy") == "on"

        settings = []
        if shuffle:
            settings.append("shuffle_questions")
        if disable_copy:
            settings.append("disable_copy_paste")

        security_json = json.dumps(settings)

        cur.execute("""
            UPDATE exams
            SET security_settings = ?, updated_at = CURRENT_TIMESTAMP
            WHERE exam_id = ?
        """, (security_json, exam_id))

        conn.commit()
        conn.close()

        flash("Security updated!", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    # -------- GET REQUEST --------
    cur.execute("SELECT * FROM exams WHERE exam_id = ?", (exam_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    # ALWAYS define exam
    exam = dict(row)

    # Safely parse JSON
    try:
        exam["security_settings"] = json.loads(exam["security_settings"] or "[]")
    except json.JSONDecodeError:
        exam["security_settings"] = []

    return render_template("set_security.html", exam=exam, exam_id=exam_id)

# -----------------------------
# AVAILABILITY UI
# -----------------------------
@examBp.route("/<int:exam_id>/availability", methods=["GET", "POST"])
def set_availability_ui(exam_id):

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        opens_dt = _parse_datetime(request.form.get("opens_at"))
        closes_dt = _parse_datetime(request.form.get("closes_at"))

        if not opens_dt or not closes_dt:
            flash("Invalid dates", "danger")
            return redirect(request.url)

        if closes_dt <= opens_dt:
            flash("Closing must be after opening", "danger")
            return redirect(request.url)

        if closes_dt < datetime.now():
            flash("Cannot set availability in the past", "danger")
            return redirect(request.url)

        cur.execute("""
            UPDATE exams
            SET opens_at = ?, closes_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE exam_id = ?
        """, (opens_dt.strftime("%Y-%m-%dT%H:%M"),
              closes_dt.strftime("%Y-%m-%dT%H:%M"),
              exam_id))

        conn.commit()
        conn.close()

        flash("Availability updated!", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    cur.execute("SELECT * FROM exams WHERE exam_id = ?", (exam_id,))
    exam = cur.fetchone()

    conn.close()

    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    return render_template("set_time_limit.html", exam=exam, exam_id=exam_id)


# -----------------------------
# REORDER QUESTIONS (Drag & Drop)
# -----------------------------
@examBp.route("/<int:exam_id>/reorder", methods=["POST"])
def reorder_questions(exam_id):
    data = request.get_json(silent=True) or {}
    order_list = data.get("order", [])

    if not isinstance(order_list, list):
        return jsonify(error="Invalid order format"), 400

    conn = get_db()
    cur = conn.cursor()

    for item in order_list:
        q_id = item.get("question_id")
        idx = item.get("order_index")

        if q_id and idx:
            cur.execute("""
                UPDATE questions
                SET order_index = ?, updated_at = CURRENT_TIMESTAMP
                WHERE question_id = ?
            """, (idx, q_id))

    conn.commit()
    conn.close()

    return jsonify(message="Order updated"), 200


# -----------------------------
# EDIT QUESTION
# -----------------------------
@examBp.route("/questions/<int:question_id>/edit_ui", methods=["GET", "POST"])
def edit_question_ui(question_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT exam_id, question_text, is_multiple_correct, points
        FROM questions
        WHERE question_id = ?
    """, (question_id,))
    q = cur.fetchone()

    if not q:
        conn.close()
        flash("Question not found", "danger")
        return redirect(url_for("home"))

    cur.execute("""
        SELECT option_id, option_text, is_correct
        FROM options
        WHERE question_id = ?
    """, (question_id,))
    options = cur.fetchall()

    exam_id = q["exam_id"]

    if request.method == "POST":
        new_text = request.form.get("question_text", "").strip()
        is_multiple = request.form.get("is_multiple") == "on"

        conn2 = get_db()
        cur2 = conn2.cursor()

        cur2.execute("""
            UPDATE questions
            SET question_text = ?, is_multiple_correct = ?, updated_at = CURRENT_TIMESTAMP
            WHERE question_id = ?
        """, (new_text, 1 if is_multiple else 0, question_id))

        # Remove old options
        cur2.execute("DELETE FROM options WHERE question_id = ?", (question_id,))

        # Insert new options
        for i in range(1, 5):
            txt = request.form.get(f"opt{i}", "").strip()
            if txt:
                is_correct = request.form.get(f"opt{i}_correct") == "on"
                cur2.execute("""
                    INSERT INTO options (question_id, option_text, is_correct)
                    VALUES (?, ?, ?)
                """, (question_id, txt, 1 if is_correct else 0))

        conn2.commit()
        conn2.close()

        flash("Question updated!", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    conn.close()
    return render_template("edit_question.html", q=q, options=options)


# -----------------------------
# DELETE QUESTION
# -----------------------------
@examBp.route("/questions/<int:question_id>/delete", methods=["POST"])
def delete_question_ui(question_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT exam_id FROM questions WHERE question_id = ?", (question_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        flash("Question not found", "danger")
        return redirect(url_for("home"))

    exam_id = row["exam_id"]

    cur.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
    cur.execute("DELETE FROM questions WHERE question_id = ?", (question_id,))

    conn.commit()
    conn.close()

    flash("Question deleted", "success")
    return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))
