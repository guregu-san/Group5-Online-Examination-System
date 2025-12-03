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
def _create_exam_in_db(course_code, instructor_email, title, time_limit, security_settings):
    """
    Shared logic used by both the UI route and the JSON API
    Returns (success_bool, result_or_error, status_code)
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

    # create exam
    cur.execute(
        """
        INSERT INTO exams (course_code, instructor_email, title, time_limit, security_settings,
                           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (course_code, instructor_email, title or "Untitled Exam", time_limit, security_settings or "")
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
    Exam Creation – UI version.
    User can type instructor NAME or EMAIL.
    """
    form = ExamCreateForm()

    if form.validate_on_submit():
        course_code = form.course_code.data.strip()
        instructor_input = form.instructor_email.data.strip()
        title = form.title.data.strip()
        time_limit = form.time_limit.data
        security_settings = form.security_settings.data.strip() if form.security_settings.data else ""

        # Resolve name -> email if needed
        instructor_email = instructor_input
        if "@" not in instructor_input:  # looks like a name
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT email FROM instructors WHERE name = ?", (instructor_input,))
            row = cur.fetchone()
            conn.close()
            if not row:
                flash("Instructor with that name not found. Use your email or check spelling.", "danger")
                return render_template("exam_create.html", form=form)
            instructor_email = row["email"]

        success, result, status = _create_exam_in_db(
            course_code, instructor_email, title, time_limit, security_settings
        )

        if not success:
            flash(result, "danger")
        else:
            flash(f"Exam created successfully! (ID: {result['exam_id']})", "success")
            # After create, go to the exam editor page (next steps)
            return redirect(url_for("examBp.edit_exam_ui", exam_id=result["exam_id"]))

    return render_template("exam_create.html", form=form)
@examBp.route("/<int:exam_id>/questions/new", methods=["GET", "POST"])
def add_question_ui(exam_id):
    """
    Add Question UI (supports different types, posts to DB).
    """
    if request.method == "POST":
        q_type = request.form.get("question_type")
        question_text = request.form.get("question_text", "").strip()

        if not question_text:
            flash("Question text is required.", "danger")
            return redirect(request.url)

        options = []
        is_multiple_correct = False

        if q_type == "mcq":
            # 4 options with checkboxes
            for i in range(1, 5):
                text = request.form.get(f"opt{i}", "").strip()
                if not text:
                    continue
                is_correct = request.form.get(f"opt{i}_correct") == "on"
                options.append({"option_text": text, "is_correct": is_correct})
            # single correct by default
            is_multiple_correct = request.form.get("allow_multiple") == "on"

        elif q_type == "true_false":
            correct_value = request.form.get("tf_answer")  # "true" or "false"
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

        # ---- Insert into DB using same logic as API ----
        if not options:
            flash("At least one answer/option is required.", "danger")
            return redirect(request.url)

        conn = get_db()
        cur = conn.cursor()

        # validate exam exists
        cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
        if not cur.fetchone():
            conn.close()
            flash("Exam not found.", "danger")
            return redirect(url_for("examBp.create_exam_ui"))

        # find next order index
        cur.execute("SELECT COALESCE(MAX(order_index), 0) FROM questions WHERE exam_id = ?", (exam_id,))
        current_max = cur.fetchone()[0]
        order_index = current_max + 1

        # insert question
        cur.execute(
            """
            INSERT INTO questions (exam_id, question_text, is_multiple_correct, points, order_index)
            VALUES (?, ?, ?, ?, ?)
            """,
            (exam_id, question_text, 1 if is_multiple_correct else 0, 1, order_index),
        )
        question_id = cur.lastrowid

        # insert options
        for opt in options:
            cur.execute(
                """
                INSERT INTO options (question_id, option_text, is_correct)
                VALUES (?, ?, ?)
                """,
                (question_id, opt["option_text"], 1 if opt["is_correct"] else 0),
            )

        # update exam timestamp
        cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))
        conn.commit()
        conn.close()

        flash("Question added successfully.", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    # GET – just render empty form
    return render_template("add_question.html", exam_id=exam_id)
@examBp.route("/<int:exam_id>/time_limit", methods=["GET", "POST"])
def set_time_limit_ui(exam_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        value = request.form.get("time_limit")
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            minutes = None

        if not minutes or minutes <= 0:
            flash("Please enter a valid positive number of minutes.", "danger")
        else:
            cur.execute(
                "UPDATE exams SET time_limit = ?, updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?",
                (minutes, exam_id),
            )
            conn.commit()
            conn.close()
            flash("Time limit updated.", "success")
            return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    # GET – show current
    cur.execute("SELECT title, time_limit FROM exams WHERE exam_id = ?", (exam_id,))
    exam = cur.fetchone()
    conn.close()
    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    return render_template("set_time_limit.html", exam=exam, exam_id=exam_id)


@examBp.route("/<int:exam_id>/security", methods=["GET", "POST"])
def set_security_ui(exam_id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        shuffle = request.form.get("shuffle") == "on"
        disable_copy = request.form.get("disable_copy") == "on"

        # store as simple text string
        settings = []
        if shuffle:
            settings.append("shuffle_questions")
        if disable_copy:
            settings.append("disable_copy_paste")
        security_str = ",".join(settings)

        cur.execute(
            "UPDATE exams SET security_settings = ?, updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?",
            (security_str, exam_id),
        )
        conn.commit()
        conn.close()
        flash("Security settings updated.", "success")
        return redirect(url_for("examBp.edit_exam_ui", exam_id=exam_id))

    # GET
    cur.execute("SELECT title, security_settings FROM exams WHERE exam_id = ?", (exam_id,))
    exam = cur.fetchone()
    conn.close()
    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    current = exam["security_settings"] or ""
    return render_template("set_security.html", exam=exam, exam_id=exam_id, current=current)
@examBp.route("/<int:exam_id>/preview", methods=["GET"])
def preview_exam_ui(exam_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT exam_id, title, time_limit, security_settings
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
@examBp.route("/<int:exam_id>/saved", methods=["GET"])
def exam_saved_ui(exam_id):
    return render_template("exam_saved.html", exam_id=exam_id)

# -----------------------------
# JSON API ROUTES
# -----------------------------

# U3-F1: Create exam (JSON)
@examBp.route("", methods=["POST"])
def create_exam():
    data = request.get_json(silent=True) or {}
    course_code = data.get("course_code")
    instructor_email = data.get("instructor_email")
    title = data.get("title", "Untitled Exam")
    time_limit = data.get("time_limit")
    security_settings = data.get("security_settings", "")

    success, result, status = _create_exam_in_db(
        course_code, instructor_email, title, time_limit, security_settings
    )

    if not success:
        return jsonify(error=result), status

    return jsonify(message="Exam created", exam_id=result["exam_id"]), status


# U3-F2: Add question
@examBp.route("/<int:exam_id>/questions", methods=["POST"])
def add_question(exam_id):
    data = request.get_json(silent=True) or {}
    question_text = data.get("question_text")
    is_multiple_correct = data.get("is_multiple_correct", False)
    points = int(data.get("points", 1))
    options = data.get("options", [])

    if not question_text:
        return jsonify(error="question_text is required"), 400
    if not isinstance(options, list) or len(options) == 0:
        return jsonify(error="At least one option is required"), 400

    # normalize boolean
    if isinstance(is_multiple_correct, str):
        is_multiple_correct = is_multiple_correct.lower() in ("true", "1", "yes", "on")

    conn = get_db()
    cur = conn.cursor()

    # validate exam exists
    cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify(error="Exam not found"), 404

    # enforce correct_answer rules
    correct_count = sum(1 for opt in options if opt.get("is_correct"))
    if not is_multiple_correct and correct_count != 1:
        conn.close()
        return jsonify(error="Single-correct question must have exactly one correct option"), 400

    # find next order_index
    cur.execute("SELECT COALESCE(MAX(order_index), 0) FROM questions WHERE exam_id = ?", (exam_id,))
    current_max = cur.fetchone()[0]
    order_index = current_max + 1

    # insert question
    cur.execute(
        """
        INSERT INTO questions (exam_id, question_text, is_multiple_correct, points, order_index)
        VALUES (?, ?, ?, ?, ?)
        """,
        (exam_id, question_text, int(is_multiple_correct), points, order_index)
    )
    question_id = cur.lastrowid

    # insert options
    for opt in options:
        cur.execute(
            """
            INSERT INTO options (question_id, option_text, is_correct)
            VALUES (?, ?, ?)
            """,
            (
                question_id,
                opt.get("option_text", ""),
                1 if opt.get("is_correct") else 0
            )
        )

    # update exam timestamp
    cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))
    conn.commit()
    conn.close()

    return jsonify(message="Question added", question_id=question_id), 201


# U3-F3: Edit question
@examBp.route("/questions/<int:question_id>", methods=["PATCH"])
def edit_question(question_id):
    data = request.get_json(silent=True) or {}

    conn = get_db()
    cur = conn.cursor()

    # validate question exists
    cur.execute("SELECT exam_id FROM questions WHERE question_id = ?", (question_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Question not found"), 404
    exam_id = row["exam_id"]

    fields = []
    values = []

    if "question_text" in data:
        fields.append("question_text = ?")
        values.append(data["question_text"])

    if "points" in data:
        fields.append("points = ?")
        values.append(int(data["points"]))

    if "is_multiple_correct" in data:
        val = data["is_multiple_correct"]
        if isinstance(val, str):
            val = val.lower() in ("true", "1", "yes", "on")
        fields.append("is_multiple_correct = ?")
        values.append(1 if val else 0)

    if fields:
        sql = f"UPDATE questions SET {', '.join(fields)} WHERE question_id = ?"
        values.append(question_id)
        cur.execute(sql, values)

    # replace options
    if "options" in data:
        options = data["options"]
        if not isinstance(options, list) or not options:
            conn.close()
            return jsonify(error="options must be a non-empty list"), 400

        # enforce valid correct-answer count
        cur.execute("SELECT is_multiple_correct FROM questions WHERE question_id = ?", (question_id,))
        qrow = cur.fetchone()
        is_multiple_correct = bool(qrow["is_multiple_correct"])
        correct_count = sum(1 for o in options if o.get("is_correct"))

        if not is_multiple_correct and correct_count != 1:
            conn.close()
            return jsonify(error="Single-correct question must have exactly one correct option"), 400

        cur.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
        for opt in options:
            cur.execute(
                """
                INSERT INTO options (question_id, option_text, is_correct)
                VALUES (?, ?, ?)
                """,
                (
                    question_id,
                    opt.get("option_text", ""),
                    1 if opt.get("is_correct") else 0
                )
            )

    # update timestamp
    cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))
    conn.commit()
    conn.close()

    return jsonify(message="Question updated"), 200


# U3-F4: Delete question
@examBp.route("/questions/<int:question_id>", methods=["DELETE"])
def delete_question(question_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT exam_id FROM questions WHERE question_id = ?", (question_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Question not found"), 404
    exam_id = row["exam_id"]

    cur.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
    cur.execute("DELETE FROM questions WHERE question_id = ?", (question_id,))
    cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))

    conn.commit()
    conn.close()

    return jsonify(message="Question deleted"), 200


# U3-F5: Reorder questions
@examBp.route("/<int:exam_id>/reorder", methods=["POST"])
def reorder_questions(exam_id):
    data = request.get_json(silent=True) or {}
    order = data.get("order", [])

    if not isinstance(order, list):
        return jsonify(error="order must be a list"), 400

    conn = get_db()
    cur = conn.cursor()

    # validate exam exists
    cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify(error="Exam not found"), 404

    for item in order:
        qid = item.get("question_id")
        idx = item.get("order_index")
        if qid is None or idx is None:
            continue
        cur.execute(
            "UPDATE questions SET order_index = ? WHERE question_id = ? AND exam_id = ?",
            (int(idx), int(qid), exam_id)
        )

    cur.execute("UPDATE exams SET updated_at = CURRENT_TIMESTAMP WHERE exam_id = ?", (exam_id,))
    conn.commit()
    conn.close()

    return jsonify(message="Order updated"), 200


# U3-F6: Update exam options
@examBp.route("/<int:exam_id>/options", methods=["PATCH"])
def update_exam_options(exam_id):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []

    if "title" in data:
        fields.append("title = ?")
        values.append(data["title"])

    if "time_limit" in data:
        fields.append("time_limit = ?")
        values.append(int(data["time_limit"]))

    if "security_settings" in data:
        fields.append("security_settings = ?")
        values.append(data["security_settings"])

    if not fields:
        return jsonify(message="No changes"), 200

    sql = f"""
        UPDATE exams
        SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE exam_id = ?
    """
    values.append(exam_id)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT exam_id FROM exams WHERE exam_id = ?", (exam_id,))
    if not cur.fetchone():
        conn.close()
        return jsonify(error="Exam not found"), 404

    cur.execute(sql, values)
    conn.commit()
    conn.close()

    return jsonify(message="Exam options updated"), 200


# U3-F7: List exams by instructor
@examBp.route("/instructor/<path:email>", methods=["GET"])
def list_exams_by_instructor(email):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT exam_id, title, course_code, time_limit, security_settings,
               created_at, updated_at
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
    """
    Show exam editing interface:
    - exam name
    - time limit
    - security settings
    - list of questions
    """
    conn = get_db()
    cur = conn.cursor()

    # get exam info
    cur.execute("""
        SELECT exam_id, title, time_limit, security_settings
        FROM exams
        WHERE exam_id = ?
    """, (exam_id,))
    exam = cur.fetchone()
    if not exam:
        conn.close()
        flash("Exam not found.", "danger")
        return redirect(url_for("examBp.create_exam_ui"))

    # get questions
    cur.execute("""
        SELECT q.question_id, q.question_text, q.is_multiple_correct, q.order_index
        FROM questions q
        WHERE q.exam_id = ?
        ORDER BY q.order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()
    conn.close()

    return render_template(
        "exam_edit.html",
        exam=exam,
        questions=questions
    )
