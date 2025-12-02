import sqlite3
import json
from flask import Blueprint, render_template, redirect, url_for, jsonify, request, session

from app.take_exam.forms import ExamSearchForm, ExamInitializationForm, SubmissionForm
from app.models import db, Students, Instructors, Courses, Exams, Questions, Options, Submissions

takeExamBp = Blueprint("takeExamBp", __name__, url_prefix="/take_exam",  template_folder="templates")

'''Utility functions'''
def get_db(): # Connect to the SQLite database
    conn = sqlite3.connect("oesDB.db")
    conn.row_factory = sqlite3.Row # Allow row access by column name
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn

def row_to_dict(row): # Convert SQLite row to dictionary
    return {k: row[k] for k in row.keys()}

def calculate_score(exam_id, answers_dict):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT question_id, points FROM questions WHERE exam_id=?", (exam_id,))
    questions = cur.fetchall()

    total_score = 0

    for q in questions:
        qid = q["question_id"]
        key = str(qid)

        selected = answers_dict.get(key, [])
        if isinstance(selected, int):
            selected = [selected]
        selected = set(map(int, selected)) if selected else set()

        cur.execute("SELECT option_id, is_correct FROM options WHERE question_id=?", (qid,))
        rows = cur.fetchall()
        correct = {r["option_id"] for r in rows if r["is_correct"] == 1}

        if selected == correct and len(correct) > 0:
            total_score += q["points"]

    conn.close()
    return total_score

'''Routes'''
# Find the exam
@takeExamBp.route('', methods=['GET', 'POST'])
def exam_search():
    form = ExamSearchForm()
    if form.validate_on_submit():
        exam_id = form.examID.data
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT exam_id FROM exams WHERE exam_id=?", (exam_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            form.examID.errors = ("Exam not found.",)
            return render_template('exam_search.html', form=form)

        # Store exam_id in session as a cookie
        session['exam_id'] = row['exam_id']
        return redirect(url_for('takeExamBp.exam_initialization'))

    return render_template('exam_search.html', form=form)

# Show exam info and prompt to start
@takeExamBp.route('/exam_initialization', methods=['GET', 'POST'])
def exam_initialization():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('takeExamBp.exam_search'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT exam_id, title, time_limit, course_code
        FROM exams WHERE exam_id=?
    """, (exam_id,))
    exam = cur.fetchone()
    conn.close()

    if not exam:
        session.pop('exam_id', None)
        return redirect(url_for('takeExamBp.exam_search'))

    form = ExamInitializationForm()
    if form.validate_on_submit():
        return redirect(url_for('takeExamBp.start'))

    return render_template('exam_initialization.html', form=form, exam=row_to_dict(exam))

# Show exam questions
@takeExamBp.route('/start', methods=['GET', 'POST'])
def start():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('takeExamBp.exam_search'))

    conn = get_db()
    cur = conn.cursor()

    # Fetch exam
    cur.execute("SELECT exam_id, title, time_limit FROM exams WHERE exam_id=?", (exam_id,))
    exam = cur.fetchone()
    if not exam:
        session.pop('exam_id', None)
        conn.close()
        return redirect(url_for('takeExamBp.exam_search'))

    # Fetch exam questions
    cur.execute("""
        SELECT question_id, question_text, is_multiple_correct, points, order_index
        FROM questions WHERE exam_id=?
        ORDER BY order_index ASC
    """, (exam_id,))
    questions = cur.fetchall()

    # Fetch options for each question
    questions_with_options = [] # 2D structure because each question has multiple options
    for q in questions:
        cur.execute("""
            SELECT option_id, option_text
            FROM options WHERE question_id=?
        """, (q['question_id'],))
        options = cur.fetchall()
        q_dict = row_to_dict(q)
        q_dict['options'] = [row_to_dict(o) for o in options]
        questions_with_options.append(q_dict)

    conn.close()

    form = SubmissionForm()

    # Populate the dynamic form with questions
    for i, q in enumerate(questions_with_options):

        # Append new question subform if needed
        if i >= len(form.questions):
            form.questions.append_entry()

        subform = form.questions[i]
        subform.question_id.data = q['question_id']
        choices = [(int(opt['option_id']), opt['option_text']) for opt in q['options']]

        if q['is_multiple_correct']:
            subform.single_or_multi.data = 'multi'
            subform.answer_multi.choices = choices
        else:
            subform.single_or_multi.data = 'single'
            subform.answer_single.choices = choices

        print ("Added question", q['question_id'], "with choices", choices)

    if form.validate_on_submit():
        # Collect answers
        answers = {}
        print ("Submission validated")
        for subform in form.questions:
            qid = subform.question_id.data

            if subform.single_or_multi.data == 'multi':
                answers[qid] = subform.answer_multi.data
            else:
                answers[qid] = subform.answer_single.data

        print("Collected answers:", answers)
        # TODO: calculate score and store submission in DB
        return jsonify(message="Exam submitted", answers=answers), 200

    return render_template('submission.html', form=form, exam=row_to_dict(exam), questions=questions_with_options)
