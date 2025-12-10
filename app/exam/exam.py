import sqlite3
import json
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
# INTERNAL SHARED LOGIC
# -----------------------------
def _create_exam_in_db(course_code, instructor_email, title, opens_at, closes_at, security_settings):
    """
    Insert a new exam using opens_at / closes_at instead of time_limit.
    """

    if not course_code or not instructor_email:
        return False, "course_code and instructor_email are required", 400

    conn = get_db()
    cur = conn.cursor()

    # validate instructor
    cur.execute("SELECT email FROM instructors WHERE email = ?", (instructor_email,))
    if not cur.fetchone():
        conn.close()
        return False, "Instructor does not exist", 400

    # validate course
    cur.execute("SELECT course_code, instructor_email FROM courses WHERE course_code = ?", (course_code,))
    course = cur.fetchone()
    if not course:
        conn.close()
        return False, "Course does not exist", 400

    # enforce course belongs to instructor
    if course["instructor_email"] != instructor_email:
        conn.close()
        return False, "Instructor is not assigned to this course", 400

    # create exam (NO time_limit)
    cur.execute(
        """
        INSERT INTO exams (
            course_code, instructor_email, title, security_settings,
            opens_at, closes_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (course_code, instructor_email, title or "Untitled Exam",
         security_settings or "", opens_at, closes_at)
    )

    exam_id = cur.lastrowid
    conn.commit()
    conn.close()

    return True, {"exam_id": exam_id}, 201


# -----------------------------
# UI ROUTES (HTML PAGES)
# -----------------------------
@examBp.route("/create", methods=["GET", "POST"])
def create_exam_ui():
    """
    Exam Creation (UI)
    """
    form = ExamCreateForm()

    if form.validate_on_submit():
        course_code = form.course_code.data.strip()
        instructor_input = form.instructor_email.data.strip()
        title = form.title.data.strip()

        opens_at = form.opens_at.data
        closes_at = form.closes_at.data

        security_settings = form.security_settings.data.strip() if form.security_settings.data else ""

        # Resolve instructor name → email if needed
        instructor_email = instructor_input
        if "@" not in instructor_input:  
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT email FROM instructors WHERE name = ?", (instructor_input,))
            row = cur.fetchone()
            conn.close()
            if not row:
                flash("Instructor with that name not found.", "danger")
                return render_template("exam_create.html", form=form)
            instructor_email = row["email"]

        success, result, status = _create_exam_in_db(
            course_code, instructor_email, title, opens_at, closes_at, security_settings
        )

        if not success:
            flash(result, "danger")
        else:
            flash(f"Exam created successfully! (ID: {result['exam_id']})", "success")
            return redirect(url_for("examBp.edit_exam_ui", exam_id=result["exam_id"]))

    return render_template("exam_create.html", form=form)


# -------------------------------------------------------------------
# ADD QUESTION UI
# -------------------------------------------------------------------
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

        if q_type == "mcq":
            for i in range(1, 5):
                text = request.form.get(f"opt{i}", "").strip()
                if not text:
                    continue
                is_correct = request.form.get(f"opt{i}_correct") == "on"
                options.append({"option_text": text, "is_correct": is_correct})
            is_multiple_correct = request.form.get("allow_multiple") == "on"

        elif q_type == "true_false":
            correct_value = request.form.get("tf_answer")
            options = [
                {"option_text": "True", "is_correct": correct_value == "true"},
                {"option_text": "False", "is_correct": correct_value == "false"},
            ]

        elif q_type in ["short", "numerical", "essay"]:
            answer_text = request.form.get("text_answer", "").strip()
            options = [{"option_text": answer_text, "is_correct": True}]
        else:
            flash("Invalid question type.", "danger")
            return redirect(request.url)

        if not options:
            flash("At least one answer/option is required.", "danger")
            return redirect(request.url)

        conn = get_db()
        cur = conn.cursor()

        # Validate exam
        cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
        if not cur.fetchone():
            conn.close()
            flash("Exam not found.", "danger")
            return redirect(url_for("examBp.create_exam_ui"))

        # Find next order index
        cur.execute("SELECT COALESCE(MAX(order_index), 0) FROM questions WHERE exam_id = ?", (exam_id,))
        order_index = cur.fetchone()[0] + 1

        # Insert question
        cur.execute(
            """
            INSERT INTO questions (exam_id, question_text, is_multiple_correct, points, order_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            (exam_id, question_text, 1 if is_multiple_correct else 0, 1, order_index)
        )
        question_id = cur.lastrowid

        # Insert options
        for opt in options:
            cur.execute(
                "INSERT INTO options (question_id, option_text, is_correct) VALUES (?, ?, ?)",
                (question_id, opt["option_text"], 1 if opt["is_correct"] else 0)
            )

        cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))
        conn.commit()
        conn.close()

        flash("Question added successfully.", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    return render_template("add_question.html", exam_id=exam_id)


# -------------------------------------------------------------------
# EXAM PREVIEW
# -------------------------------------------------------------------
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
        SELECT q.order_index, q.question_text
        FROM questions q
        WHERE q.exam_id = ?
        ORDER BY q.order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()
    conn.close()

    return render_template("exam_preview.html", exam=exam, questions=questions, exam_id=exam_id)


# -------------------------------------------------------------------
# JSON API ROUTES
# -------------------------------------------------------------------
@examBp.route("", methods=["POST"])
def create_exam():
    data = request.get_json(silent=True) or {}
    course_code = data.get("course_code")
    instructor_email = data.get("instructor_email")
    title = data.get("title", "Untitled Exam")

    opens_at = data.get("opens_at")
    closes_at = data.get("closes_at")
    security_settings = data.get("security_settings", "")

    success, result, status = _create_exam_in_db(
        course_code, instructor_email, title,
        opens_at, closes_at, security_settings
    )

    if not success:
        return jsonify(error=result), status

    return jsonify(message="Exam created", exam_id=result["exam_id"]), status


# -------------------------------------------------------------------
# LIST & EDIT ROUTES
# -------------------------------------------------------------------
@examBp.route("/instructor/<path:email>", methods=["GET"])
def list_exams_by_instructor(email):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT exam_id, title, course_code, opens_at, closes_at,
               security_settings, created_at, updated_at
        FROM exams
        WHERE instructor_email = ?
        ORDER BY created_at DESC
        """,
        (email,)
    )
    rows = cur.fetchall()
    conn.close()

    return jsonify([row_to_dict(r) for r in rows]), 200


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
        SELECT q.question_id, q.question_text, q.is_multiple_correct, q.order_index
        FROM questions q
        WHERE q.exam_id = ?
        ORDER BY q.order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()

    conn.close()

    return render_template("exam_edit.html", exam=exam, questions=questions)
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

        security_str = ",".join(settings)

        cur.execute("""
            UPDATE exams
            SET security_settings = ?, updated_at = CURRENT_TIMESTAMP
            WHERE exam_id = ?
        """, (security_str, exam_id))

        conn.commit()
        conn.close()

        flash("Security settings updated.", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    cur.execute("SELECT * FROM exams WHERE exam_id = ?", (exam_id,))
    exam = cur.fetchone()
    conn.close()

    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    return render_template("set_security.html", exam=exam, exam_id=exam_id)
@examBp.route("/<int:exam_id>/availability", methods=["GET", "POST"])
def set_availability_ui(exam_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        opens_at = request.form.get("opens_at")
        closes_at = request.form.get("closes_at")

        cur.execute("""
            UPDATE exams
            SET opens_at = ?, closes_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE exam_id = ?
        """, (opens_at, closes_at, exam_id))

        conn.commit()
        conn.close()

        flash("Availability updated.", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    cur.execute("SELECT * FROM exams WHERE exam_id = ?", (exam_id,))
    exam = cur.fetchone()
    conn.close()

    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    return render_template("set_time_limit.html", exam=exam, exam_id=exam_id)
