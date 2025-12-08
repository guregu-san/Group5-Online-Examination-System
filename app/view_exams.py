import sqlite3
import json
from flask import Blueprint, request, jsonify, render_template
from flask_login import current_user, login_required
#from app import app


# ---- DB helper ---- IDK WHAT THE HELL THIS IS FOR ----
def get_db():
    conn = sqlite3.connect("oesDB.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ---- Blueprint ---- IDK WHAT THE HELL THIS IS FOR ----
exam_viewBp = Blueprint('exam_view', __name__, template_folder='templates')


# U6-F1: List completed exams (results) for a student
@exam_viewBp.route('/results', methods=['GET'])
@login_required
def list_results():
    # Prefer current user when available:
    # - Students should only see their own results (use current_user.roll_number)
    # - Instructors will see results for exams they own (filtered by instructor_email) and can search by roll_number or student name
    roll_number = request.args.get('roll_number')
    course_code = request.args.get('course_code')
    instructor_name = request.args.get('instructor')
    student_name = request.args.get('student_name')
    student_roll = request.args.get('student_roll')

    # If a logged-in student is requesting results, always use their roll_number
    if current_user.is_authenticated and getattr(current_user, "role", None) == "Student":
        roll_number = getattr(current_user, "roll_number", roll_number)

    # If not a logged-in instructor and no roll_number available, require it
    if not roll_number and not (
        current_user.is_authenticated and getattr(current_user, "role", None) == "Instructor"
    ):
        return "roll_number query parameter is required for now", 400

    conn = get_db()
    cur = conn.cursor()

    # Build SQL based on whether the current user is an instructor or we have a roll_number
    base_select = """
        SELECT
            s.submission_id,
            s.exam_id,
            s.total_score,
            (SELECT COALESCE(SUM(points),0) FROM questions q WHERE q.exam_id = e.exam_id) AS total_points,
            s.status,
            s.submitted_at,
            e.title,
            e.course_code,
            c.course_name,
            i.name AS instructor_name,
            i.email AS instructor_email,
            st.name AS student_name,
            st.roll_number
        FROM submissions s
        JOIN exams e ON e.exam_id = s.exam_id
        JOIN courses c ON c.course_code = e.course_code
        JOIN instructors i ON i.email = e.instructor_email
        JOIN students st ON st.roll_number = s.roll_number
    """

    params = []

    # Determine which branch to use based on current user's actual role
    if current_user.is_authenticated and getattr(current_user, "role", None) == "Instructor":
        # Instructor view: show submissions for exams they own
        query = base_select + " WHERE e.instructor_email = ? AND s.status IN ('SUBMITTED', 'GRADED', 'IN_REVIEW', 'REVIEWED')"
        params = [current_user.email]
        
        # Add instructor-specific search filters
        if course_code:
            query += " AND e.course_code LIKE ?"
            params.append(f"%{course_code}%")
        
        if student_roll:
            query += " AND s.roll_number = ?"
            params.append(student_roll)
        
        if student_name:
            query += " AND st.name LIKE ?"
            params.append(f"%{student_name}%")
    else:
        # Student view: show only their own REVIEWED results
        if not roll_number:
            # If student is logged in, use their roll_number
            roll_number = getattr(current_user, "roll_number", None)
        
        if not roll_number:
            return "roll_number query parameter is required", 400
            
        query = base_select + " WHERE s.roll_number = ? AND s.status = 'REVIEWED'"
        params = [roll_number]
        
        # Add student-specific search filters
        if course_code:
            query += " AND e.course_code LIKE ?"
            params.append(f"%{course_code}%")

        if instructor_name:
            query += " AND i.name LIKE ?"
            params.append(f"%{instructor_name}%")

    query += " ORDER BY s.submitted_at DESC"

    print(f"DEBUG - User role: {getattr(current_user, 'role', 'NONE')}")
    print(f"DEBUG - Query: {query}")
    print(f"DEBUG - Params: {params}")
    
    cur.execute(query, params)
    rows = cur.fetchall()
    # convert rows to dicts
    results = [row_to_dict(r) for r in rows]
    
    print(f"DEBUG - Results count: {len(results)}")
    
    conn.close()

    # HTML-view
    return render_template(
        'view_results.html',
        results=results,
        roll_number=roll_number,
        course_code=course_code or "",
        instructor_name=instructor_name or "",
        current_user=current_user
    )


# JSON API for testing
@exam_viewBp.route('/api/results', methods=['GET'])
def api_list_results():
    roll_number = request.args.get('roll_number')
    if not roll_number:
        return jsonify(error="roll_number required"), 400

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.submission_id,
            s.exam_id,
            s.total_score,
            s.status,
            s.submitted_at,
            e.title,
            e.course_code
        FROM submissions s
        JOIN exams e ON e.exam_id = s.exam_id
        WHERE s.roll_number = ?
          AND s.status IN ('SUBMITTED', 'GRADED')
        ORDER BY s.submitted_at DESC
    """, (roll_number,))
    rows = cur.fetchall()
    conn.close()

    return jsonify([row_to_dict(r) for r in rows])


# U6-F2: View single exam result (grade + answers)
@exam_viewBp.route('/results/<int:submission_id>', methods=['GET'])
@login_required
def view_result_detail(submission_id):
    roll_number = request.args.get('roll_number') 

    conn = get_db()
    cur = conn.cursor()

    # fetch submission + check ownership
    cur.execute("""
        SELECT s.*, e.title, e.course_code, e.instructor_email, e.exam_id
        FROM submissions s
        JOIN exams e ON e.exam_id = s.exam_id
        WHERE s.submission_id = ?
    """, (submission_id,))
    sub = cur.fetchone()

    if not sub:
        conn.close()
        return "Submission not found", 404

    # Security checks based on user role
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == "Student":
            # Students can only view their own reviewed results
            if sub["roll_number"] != current_user.roll_number:
                conn.close()
                return "Not allowed to view this result", 403
            if sub["status"] != "REVIEWED":
                conn.close()
                return "This exam has not been reviewed yet", 403
        elif getattr(current_user, "role", None) == "Instructor":
            # Instructors can view results for exams they own
            if sub["instructor_email"] != current_user.email:
                conn.close()
                return "Not allowed to view this result", 403
        else:
            # Unknown role
            conn.close()
            return "Not allowed to view this result", 403
    else:
        # Not authenticated
        conn.close()
        return "Not allowed to view this result", 403

    status = sub["status"]
    exam_id = sub["exam_id"]
    total_score = sub["total_score"]
    feedback = sub["feedback"]
    answers_json = sub["answers"] or "{}"
    answers = json.loads(answers_json)

    # answers may be in two shapes:
    # - dict mapping str(question_id) -> selected option id(s) (from take_exam)
    # - list of answer dicts (from manual grading) where each entry may include
    #   question_id, auto_points, manual_points, final_points, max_points, answer_text
    is_answers_map = isinstance(answers, dict)
    answers_by_q = {}
    if not is_answers_map and isinstance(answers, list):
        for a in answers:
            try:
                qid = int(a.get("question_id"))
            except Exception:
                continue
            answers_by_q[qid] = a

    # if not graded or reviewed, show message
    if status not in ("GRADED", "REVIEWED"):
        conn.close()
        return render_template(
            'view_result_details.html',
            exam=None,
            questions=[],
            message="Exam not graded yet",
            total_score=None
        )

    # fetch questions + options
    cur.execute("""
        SELECT q.question_id, q.question_text, q.points, q.is_multiple_correct,
               o.option_id, o.option_text, o.is_correct
        FROM questions q
        LEFT JOIN options o ON o.question_id = q.question_id
        WHERE q.exam_id = ?
        ORDER BY q.order_index, o.option_id
    """, (exam_id,))
    rows = cur.fetchall()
    conn.close()

    # build structure
    questions = {}
    for r in rows:
        qid = r["question_id"]
        if qid not in questions:
            questions[qid] = {
                "question_id": qid,
                "question_text": r["question_text"],
                "points": r["points"],
                "is_multiple_correct": bool(r["is_multiple_correct"]),
                "options": []
            }
        if r["option_id"] is not None:
            questions[qid]["options"].append({
                "option_id": r["option_id"],
                "option_text": r["option_text"],
                "is_correct": bool(r["is_correct"])
            })

    # highlight selected answers
    for qid, qdata in questions.items():
        if is_answers_map:
            selected_ids = answers.get(str(qid), [])
        else:
            # try to find selected IDs in the structured answers (if present)
            entry = answers_by_q.get(qid)
            # possible keys: 'selected', 'selected_option_ids', 'answer' or nothing
            if entry is None:
                selected_ids = []
            else:
                # common shapes: list of ints, single int, or comma-separated string
                if isinstance(entry.get('selected_option_ids'), list):
                    selected_ids = entry.get('selected_option_ids')
                elif isinstance(entry.get('selected'), list):
                    selected_ids = entry.get('selected')
                elif isinstance(entry.get('answer'), list):
                    selected_ids = entry.get('answer')
                elif isinstance(entry.get('answer'), int):
                    selected_ids = [entry.get('answer')]
                else:
                    # fallback: student answer text not useful for MCQ selection
                    selected_ids = []
        if isinstance(selected_ids, int):
            selected_ids = [selected_ids]
        selected_ids = set(map(int, selected_ids)) if selected_ids else set()

        for opt in qdata["options"]:
            opt["selected_by_student"] = opt["option_id"] in selected_ids

        # determine earned points
        # If manual grading data exists for this question, prefer final_points/manual_points/auto_points
        entry = answers_by_q.get(qid) if not is_answers_map else None
        if entry is not None:
            final_p = entry.get('final_points')
            manual_p = entry.get('manual_points')
            auto_p = entry.get('auto_points')
            if final_p is not None:
                qdata['earned_points'] = float(final_p)
            elif manual_p is not None:
                qdata['earned_points'] = float(manual_p)
            elif auto_p is not None:
                qdata['earned_points'] = float(auto_p)
            else:
                # fallback to auto evaluation from selected ids when possible
                correct_ids = {o['option_id'] for o in qdata['options'] if o.get('is_correct')}
                if correct_ids and selected_ids == correct_ids:
                    qdata['earned_points'] = qdata['points']
                else:
                    qdata['earned_points'] = 0
        else:
            # no manual grading data, compute auto-earned by exact-match of selected ids
            correct_ids = {o['option_id'] for o in qdata['options'] if o.get('is_correct')}
            if correct_ids and selected_ids == correct_ids:
                qdata['earned_points'] = qdata['points']
            else:
                qdata['earned_points'] = 0

    # compute total possible points for the exam
    total_possible = sum(q['points'] for q in questions.values())

    exam_info = {
        "title": sub["title"],
        "course_code": sub["course_code"],
        "exam_id": exam_id
    }

    return render_template(
        'view_result_details.html',
        exam=exam_info,
        questions=list(questions.values()),
        total_score=total_score,
        total_possible=total_possible,
        feedback=feedback,
        message=None
    )


# register blueprint on app --- was causing issues to run project ---
#app.register_blueprint(exam_viewBp)
