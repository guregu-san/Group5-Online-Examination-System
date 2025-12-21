import sqlite3
import json
import os
from flask import Blueprint, request, jsonify

manualGradingBp = Blueprint(
    "manualGradingBp",
    __name__,
    url_prefix="/grading",
    template_folder="templates",
)


def get_db():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db_path = os.path.join(base_dir, "oesDB.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# submissions.answers JSON helpers
def load_answers_from_row(row):
    raw = row["answers"]
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "questions" in data and isinstance(data["questions"], list):
        return data["questions"]
    return []


def save_answers(conn, submission_id, answers):
    raw = json.dumps(answers)
    cur = conn.cursor()
    cur.execute(
        "UPDATE submissions SET answers = ?, updated_at = CURRENT_TIMESTAMP WHERE submission_id = ?",
        (raw, submission_id),
    )


def recalc_total_score(conn, submission_id, answers=None):
    cur = conn.cursor()

    if answers is None:
        cur.execute("SELECT answers FROM submissions WHERE submission_id = ?", (submission_id,))
        row = cur.fetchone()
        if not row:
            return None
        try:
            answers = json.loads(row["answers"]) if row["answers"] else []
        except Exception:
            answers = []

    if isinstance(answers, dict) and "questions" in answers:
        answers_list = answers["questions"]
    else:
        answers_list = answers

    total = 0.0
    for ans in answers_list:
        final_p = ans.get("final_points")
        if final_p is None:
            manual_p = ans.get("manual_points")
            auto_p = ans.get("auto_points")
            if manual_p is not None:
                final_p = manual_p
            elif auto_p is not None:
                final_p = auto_p
            else:
                final_p = 0.0
        total += float(final_p)

    cur.execute(
        "UPDATE submissions SET total_score = ?, updated_at = CURRENT_TIMESTAMP WHERE submission_id = ?",
        (total, submission_id),
    )
    return total


def find_answer_entry(answers, question_id):
    for ans in answers:
        if ans.get("question_id") == question_id:
            return ans
    return None


def get_question_max_points(conn, question_id):
    cur = conn.cursor()
    cur.execute("SELECT points FROM questions WHERE question_id = ?", (question_id,))
    row = cur.fetchone()
    if not row:
        return None
    return row["points"]


# U4-F1: Load Manual Grading Dashboard
@manualGradingBp.route("/dashboard/<path:instructor_email>", methods=["GET"])
def load_manual_grading_dashboard(instructor_email):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            e.exam_id,
            e.title,
            e.course_code,
            COUNT(s.submission_id) AS total_submissions,
            SUM(CASE WHEN s.status = 'IN_REVIEW' THEN 1 ELSE 0 END) AS in_review,
            SUM(CASE WHEN s.status = 'REVIEWED' THEN 1 ELSE 0 END) AS reviewed
        FROM exams e
        LEFT JOIN submissions s ON s.exam_id = e.exam_id
        WHERE e.instructor_email = ?
        GROUP BY e.exam_id, e.title, e.course_code
        ORDER BY e.created_at DESC
        """,
        (instructor_email,),
    )
    rows = cur.fetchall()
    conn.close()

    exams = []
    for r in rows:
        exams.append(
            {
                "exam_id": r["exam_id"],
                "title": r["title"],
                "course_code": r["course_code"],
                "total_submissions": r["total_submissions"],
                "in_review": r["in_review"],
                "reviewed": r["reviewed"],
            }
        )

    return jsonify(exams), 200


# U4-F2: List Submissions for Selected Exam
@manualGradingBp.route("/exams/<int:exam_id>/submissions", methods=["GET"])
def list_submissions(exam_id):
    status_filter = request.args.get("status")

    # If UI ever sends "GRADED", map it to DB status "REVIEWED"
    if status_filter == "GRADED":
        status_filter = "REVIEWED"

    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT
            s.submission_id,
            s.roll_number,
            st.name AS student_name,
            s.started_at,
            s.submitted_at,
            s.status,
            s.total_score
        FROM submissions s
        LEFT JOIN students st ON st.roll_number = s.roll_number
        WHERE s.exam_id = ?
    """
    params = [exam_id]

    if status_filter:
        sql += " AND s.status = ?"
        params.append(status_filter)

    sql += " ORDER BY s.submitted_at ASC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    submissions = []
    for r in rows:
        submissions.append(
            {
                "submission_id": r["submission_id"],
                "roll_number": r["roll_number"],
                "student_name": r["student_name"],
                "started_at": r["started_at"],
                "submitted_at": r["submitted_at"],
                "status": r["status"],
                "total_score": r["total_score"],
            }
        )

    return jsonify(submissions), 200


# U4-F3: Open a Submission for Review
@manualGradingBp.route("/submissions/<int:submission_id>/open", methods=["POST"])
def open_submission_for_review(submission_id):
    data = request.get_json(silent=True) or {}
    instructor_email = data.get("instructor_email")

    if not instructor_email:
        return jsonify(error="instructor_email is required"), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.*, e.title, e.course_code, e.instructor_email
        FROM submissions s
        JOIN exams e ON e.exam_id = s.exam_id
        WHERE s.submission_id = ?
        """,
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    if row["instructor_email"] != instructor_email:
        conn.close()
        return jsonify(error="You are not allowed to review this exam"), 403

    # Move SUBMITTED -> IN_REVIEW only
    if row["status"] == "SUBMITTED":
        cur.execute(
            """
            UPDATE submissions
            SET status = 'IN_REVIEW',
                updated_at = CURRENT_TIMESTAMP
            WHERE submission_id = ?
            """,
            (submission_id,),
        )
        conn.commit()

        cur.execute(
            """
            SELECT s.*, e.title, e.course_code, e.instructor_email
            FROM submissions s
            JOIN exams e ON e.exam_id = s.exam_id
            WHERE s.submission_id = ?
            """,
            (submission_id,),
        )
        row = cur.fetchone()

    answers = load_answers_from_row(row)
    submission_info = row_to_dict(row)
    submission_info["answers"] = answers

    conn.close()
    return jsonify(submission_info), 200


# U4-F4: Toggle Correct/Wrong
@manualGradingBp.route(
    "/submissions/<int:submission_id>/answers/<int:question_id>/toggle-verdict",
    methods=["POST"],
)
def toggle_verdict(submission_id, question_id):
    data = request.get_json(silent=True) or {}
    force_correct = bool(data.get("force_correct", False))
    max_points = data.get("max_points")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)
    ans = find_answer_entry(answers, question_id)

    if ans is None:
        ans = {"question_id": question_id, "answer_text": "", "auto_points": 0}
        answers.append(ans)

    if max_points is None:
        max_points = get_question_max_points(conn, question_id)
    if max_points is None:
        max_points = 0

    ans["manual_points"] = float(max_points) if force_correct else 0.0
    ans["final_points"] = ans["manual_points"]

    save_answers(conn, submission_id, answers)
    total = recalc_total_score(conn, submission_id, answers)

    conn.commit()
    conn.close()

    return jsonify(
        {
            "question_id": question_id,
            "final_points": ans["final_points"],
            "total_score": total,
        }
    ), 200


# U4-F5: Set Partial Credit
@manualGradingBp.route(
    "/submissions/<int:submission_id>/answers/<int:question_id>/manual-points",
    methods=["POST"],
)
def set_manual_points(submission_id, question_id):
    data = request.get_json(silent=True) or {}
    if "points" not in data:
        return jsonify(error="points is required"), 400

    try:
        points = float(data.get("points"))
    except (TypeError, ValueError):
        return jsonify(error="points must be a number"), 400

    conn = get_db()
    cur = conn.cursor()

    max_points = data.get("max_points")
    if max_points is None:
        max_points = get_question_max_points(conn, question_id)

    # If still None, allow it, but don’t block save
    if max_points is not None:
        if points < 0 or points > float(max_points):
            conn.close()
            return jsonify(error="points must be between 0 and max_points"), 400

    cur.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)
    ans = find_answer_entry(answers, question_id)
    if ans is None:
        ans = {"question_id": question_id, "answer_text": "", "auto_points": 0}
        answers.append(ans)

    ans["manual_points"] = points
    ans["final_points"] = points

    save_answers(conn, submission_id, answers)
    total = recalc_total_score(conn, submission_id, answers)

    conn.commit()
    conn.close()

    return jsonify(
        {
            "question_id": question_id,
            "manual_points": points,
            "final_points": points,
            "total_score": total,
        }
    ), 200


# U4-F6: Add Feedback (overall REPLACE, per-question APPEND)
@manualGradingBp.route("/submissions/<int:submission_id>/feedback", methods=["POST"])
def add_feedback(submission_id):
    data = request.get_json(silent=True) or {}
    comment = (data.get("comment") or "").strip()
    question_id = data.get("question_id")

    if comment == "":
        return jsonify(error="comment is required"), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    existing_feedback = (row["feedback"] or "").strip()

    # OVERALL feedback
    if question_id is None:
        # REPLACE overall feedback
        new_feedback = comment
    else:
        # APPEND to overall feedback
        new_feedback = (existing_feedback + "\n" + comment).strip() if existing_feedback else comment

    cur.execute(
        "UPDATE submissions SET feedback = ?, updated_at = CURRENT_TIMESTAMP WHERE submission_id = ?",
        (new_feedback, submission_id),
    )

    # Per-question feedback inside answers JSON
    if question_id is not None:
        qid = int(question_id)
        answers = load_answers_from_row(row)
        ans = find_answer_entry(answers, qid)
        if ans is None:
            ans = {"question_id": qid, "answer_text": "", "auto_points": 0}
            answers.append(ans)

        existing_q_fb = (ans.get("feedback") or "").strip()
        ans["feedback"] = (existing_q_fb + "\n" + comment).strip() if existing_q_fb else comment

        save_answers(conn, submission_id, answers)

    conn.commit()
    conn.close()

    return jsonify(message="Feedback saved", feedback=new_feedback), 201


# U4-F7: Recalculate Submission Score
@manualGradingBp.route("/submissions/<int:submission_id>/recalc", methods=["POST"])
def recalc_submission_totals(submission_id):
    conn = get_db()
    total = recalc_total_score(conn, submission_id)
    conn.commit()
    conn.close()

    if total is None:
        return jsonify(error="Submission not found"), 404

    return jsonify(total_score=total), 200


# U4-F8: Save Changes / Finalize Review
# IMPORTANT: DB allows REVIEWED (NOT GRADED)
@manualGradingBp.route("/submissions/<int:submission_id>/save", methods=["POST"])
def save_submission_review(submission_id):
    conn = get_db()
    cur = conn.cursor()

    total = recalc_total_score(conn, submission_id)
    if total is None:
        conn.close()
        return jsonify(error="Submission not found"), 404

    cur.execute(
        """
        UPDATE submissions
        SET status = 'REVIEWED',
            updated_at = CURRENT_TIMESTAMP
        WHERE submission_id = ?
        """,
        (submission_id,),
    )

    conn.commit()
    conn.close()

    # We return both DB status + a display status for frontend
    return jsonify(
        message="Submission saved",
        total_score=total,
        status="REVIEWED",
        status_display="GRADED",
    ), 200


# U4-F9: Cancel Review
@manualGradingBp.route("/submissions/<int:submission_id>/cancel", methods=["POST"])
def cancel_submission_review(submission_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT status FROM submissions WHERE submission_id = ?", (submission_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    new_status = row["status"]
    if new_status == "IN_REVIEW":
        new_status = "SUBMITTED"

    cur.execute(
        "UPDATE submissions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE submission_id = ?",
        (new_status, submission_id),
    )

    conn.commit()
    conn.close()

    return jsonify(message="Review canceled", status=new_status), 200


# U4-F10: Verify Submission Integrity
@manualGradingBp.route("/admin/submissions/<int:submission_id>/verify-integrity", methods=["POST"])
def verify_submission_integrity(submission_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)

    changed = False
    for ans in answers:
        if "final_points" not in ans or ans["final_points"] is None:
            manual_p = ans.get("manual_points")
            auto_p = ans.get("auto_points")
            if manual_p is not None:
                ans["final_points"] = manual_p
            elif auto_p is not None:
                ans["final_points"] = auto_p
            else:
                ans["final_points"] = 0.0
            changed = True

    if changed:
        save_answers(conn, submission_id, answers)

    total = recalc_total_score(conn, submission_id, answers)
    conn.commit()
    conn.close()

    return jsonify(
        message="Integrity check completed",
        total_score=total,
        answers_fixed=changed,
    ), 200
