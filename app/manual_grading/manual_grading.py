import sqlite3
import json
import os
from flask import Blueprint, request, jsonify


# Blueprint
manualGradingBp = Blueprint(
    "manualGradingBp",
    __name__,
    url_prefix="/grading",
   template_folder="templates",

)


def get_db():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # -> app/
    db_path = os.path.join(base_dir, "oesDB.db")  # -> app/oesDB.db
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn



def row_to_dict(row):
    return {k: row[k] for k in row.keys()}



# Helpers for working with submissions.answers JSON
#       "question_id": 1,
#       "answer_text": "some text",
#       "auto_points": 0,
#       "manual_points": null,
#       "final_points": 0,
#       "max_points": 2,
#       "feedback": ""
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
    if isinstance(data, dict) and "questions" in data and isinstance(
        data["questions"], list
    ):
        return data["questions"]
    return []


def save_answers(conn, submission_id, answers):
    """Save answers list back into submissions.answers as JSON string."""
    raw = json.dumps(answers)
    cur = conn.cursor()
    cur.execute(
        "UPDATE submissions SET answers = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE submission_id = ?",
        (raw, submission_id),
    )


def recalc_total_score(conn, submission_id, answers=None):
    """Recalculate submissions.total_score from answers.final_points."""
    cur = conn.cursor()
   # If caller didn't pass answers, load them from DB
    if answers is None:
        cur.execute(
            "SELECT answers FROM submissions WHERE submission_id = ?",
            (submission_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        try:
            answers = json.loads(row["answers"]) if row["answers"] else []
        except Exception:
            answers = []
 # If answers is wrapped, unwrap

    if isinstance(answers, dict) and "questions" in answers:
        answers_list = answers["questions"]
    else:
        answers_list = answers
# Sum final points for all answers
    total = 0.0
    for ans in answers_list:
        final_p = ans.get("final_points")
        if final_p is None:
            # if final not set, fall back to manual or auto
            manual_p = ans.get("manual_points")
            auto_p = ans.get("auto_points")
            if manual_p is not None:
                final_p = manual_p
            elif auto_p is not None:
                final_p = auto_p
            else:
                final_p = 0.0
        total += float(final_p)
# Store total score in the submissions table
    cur.execute(
        "UPDATE submissions SET total_score = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE submission_id = ?",
        (total, submission_id),
    )
    return total


def find_answer_entry(answers, question_id):
    """
    Find the dict in 'answers' list for a given question_id.
    If not found, return None.
    """
    for ans in answers:
        if ans.get("question_id") == question_id:
            return ans
    return None


def get_question_max_points(conn, question_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT points FROM questions WHERE question_id = ?",
        (question_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row["points"]


# U4-F1: Load Manual Grading Dashboard
@manualGradingBp.route("/dashboard/<path:instructor_email>", methods=["GET"])
def load_manual_grading_dashboard(instructor_email):
    conn = get_db()
    cur = conn.cursor()

    # Get exams for this instructor with submission counts by status
    cur.execute(
        """
        SELECT
            e.exam_id,
            e.title,
            e.course_code,
            COUNT(s.submission_id) AS total_submissions,
            SUM(CASE WHEN s.status = 'IN_REVIEW' THEN 1 ELSE 0 END) AS in_review,
            SUM(CASE WHEN s.status = 'GRADED' THEN 1 ELSE 0 END) AS graded
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
                "graded": r["graded"],
            }
        )

    return jsonify(exams), 200


# U4-F2: List Submissions for Selected Exam
@manualGradingBp.route("/exams/<int:exam_id>/submissions", methods=["GET"])
def list_submissions(exam_id):
    # Optional query parameter: ?status=SUBMITTED / IN_REVIEW / GRADED
    status_filter = request.args.get("status")

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
#   Checks if this instructor owns the exam, switches status to IN_REVIEW
#   and returns full submission data and answers.
@manualGradingBp.route("/submissions/<int:submission_id>/open", methods=["POST"])
def open_submission_for_review(submission_id):
    data = request.get_json(silent=True) or {}
    instructor_email = data.get("instructor_email")

    if not instructor_email:
        return jsonify(error="instructor_email is required"), 400

    conn = get_db()
    cur = conn.cursor()

    # Load submission + exam to verify ownership
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
  # Security check: only the exam's instructor can open it
    if row["instructor_email"] != instructor_email:
        conn.close()
        return jsonify(error="You are not allowed to review this exam"), 403

    # Mark as IN_REVIEW if currently SUBMITTED
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

      # Reload row so status is up to date in response
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


# U4-F4: Toggle Correct/Wrong (boolean override)
# Sets manual_points to full marks or 0 and updates final_points + total score.
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

    cur.execute(
        "SELECT * FROM submissions WHERE submission_id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)
    ans = find_answer_entry(answers, question_id)
    
    if ans is None:
        # create minimal entry if missing
        ans = {"question_id": question_id, "answer_text": "", "auto_points": 0}
        answers.append(ans)
 # If max_points is not provided by the frontend, look it up in DB
    if max_points is None:
        max_points = get_question_max_points(conn, question_id)
    if max_points is None:
        max_points = 0
 # If Correct → give full points; if Wrong → 0
    if force_correct:
        ans["manual_points"] = float(max_points)
    else:
        ans["manual_points"] = 0.0

    ans["final_points"] = ans["manual_points"]
  
    # Save back and recalculate
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
# Allows the instructor to manually assign any value between 0 and max_points.
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

    max_points = data.get("max_points")
    conn = get_db()
    cur = conn.cursor()
# If max_points omitted, get it from the questions table
    if max_points is None:
        max_points = get_question_max_points(conn, question_id)
    if max_points is None:
        max_points = points  # fallback

    if points < 0 or points > float(max_points):
        conn.close()
        return jsonify(error="points must be between 0 and max_points"), 400

    cur.execute(
        "SELECT * FROM submissions WHERE submission_id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)
    ans = find_answer_entry(answers, question_id)
    if ans is None:
        ans = {"question_id": question_id, "answer_text": "", "auto_points": 0}
        answers.append(ans)
# Store manual and final points
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
            "total_score": total,
        }
    ), 200


# U4-F6: Add Feedback
# Stores overall feedback in submissions.feedback (text).
@manualGradingBp.route(
    "/submissions/<int:submission_id>/feedback",
    methods=["POST"],
)
def add_feedback(submission_id):
    data = request.get_json(silent=True) or {}
    comment = (data.get("comment") or "").strip()
    question_id = data.get("question_id")

    if not comment:
        return jsonify(error="comment is required"), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM submissions WHERE submission_id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    # overall feedback in column
    existing_feedback = row["feedback"] or ""
    if existing_feedback:
        new_feedback = existing_feedback + "\n" + comment
    else:
        new_feedback = comment

    cur.execute(
        """
        UPDATE submissions
        SET feedback = ?, updated_at = CURRENT_TIMESTAMP
        WHERE submission_id = ?
        """,
        (new_feedback, submission_id),
    )

    # optional per-question feedback stored inside answers JSON
    if question_id is not None:
        answers = load_answers_from_row(row)
        ans = find_answer_entry(answers, int(question_id))
        if ans is None:
            ans = {"question_id": int(question_id), "answer_text": "", "auto_points": 0}
            answers.append(ans)
        # append comment
        existing_q_fb = ans.get("feedback") or ""
        if existing_q_fb:
            ans["feedback"] = existing_q_fb + "\n" + comment
        else:
            ans["feedback"] = comment

        save_answers(conn, submission_id, answers)

    conn.commit()
    conn.close()

    return jsonify(message="Feedback added"), 201


# U4-F7: Recalculate Submission Score
#  Just recomputes total_score from answers.final_points.
#  Useful when frontend has changed several answers.
@manualGradingBp.route(
    "/submissions/<int:submission_id>/recalc",
    methods=["POST"],
)
def recalc_submission_totals(submission_id):
    conn = get_db()
    total = recalc_total_score(conn, submission_id)
    conn.commit()
    conn.close()

    if total is None:
        return jsonify(error="Submission not found"), 404

    return jsonify(total_score=total), 200


# U4-F8: Save Changes / Finalize Review
# Recalculates total score one last time
# Sets status = 'GRADED'

@manualGradingBp.route(
    "/submissions/<int:submission_id>/save",
    methods=["POST"],
)
def save_submission_review(submission_id):
    conn = get_db()
    cur = conn.cursor()

    total = recalc_total_score(conn, submission_id)

    cur.execute(
        """
        UPDATE submissions
        SET status = 'GRADED',
            updated_at = CURRENT_TIMESTAMP
        WHERE submission_id = ?
        """,
        (submission_id,),
    )

    conn.commit()
    conn.close()

    if total is None:
        return jsonify(error="Submission not found"), 404

    return jsonify(message="Submission graded", total_score=total), 200


# U4-F9: Cancel Review
# If the submission was IN_REVIEW → revert back to SUBMITTED.
# Used when instructor presses "Cancel" and discards changes
@manualGradingBp.route(
    "/submissions/<int:submission_id>/cancel",
    methods=["POST"],
)
def cancel_submission_review(submission_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT status FROM submissions WHERE submission_id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    new_status = row["status"]
    if new_status == "IN_REVIEW":
        new_status = "SUBMITTED"

    cur.execute(
        """
        UPDATE submissions
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE submission_id = ?
        """,
        (new_status, submission_id),
    )

    conn.commit()
    conn.close()

    return jsonify(message="Review canceled", status=new_status), 200


# U4-F10: Verify Submission Integrity (IT tool)
# Ensures each answer has final_points set (fills from manual or auto).
# Recalculates total_score.
# Returns whether any answers were fixed.
@manualGradingBp.route(
    "/admin/submissions/<int:submission_id>/verify-integrity",
    methods=["POST"],
)
def verify_submission_integrity(submission_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM submissions WHERE submission_id = ?",
        (submission_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify(error="Submission not found"), 404

    answers = load_answers_from_row(row)

    # fix missing final_points
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

