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
        exam = Exams.query.get({"exam_id":form.examID.data})
        if not exam:
            form.examID.errors = ("Exam not found.",)
            return render_template('exam_search.html', form=form)

        # Store exam_id in session as a cookie
        session['exam_id'] = exam.exam_id
        return redirect(url_for('takeExamBp.exam_initialization'))

    return render_template('exam_search.html', form=form)

# Show exam info and prompt to start
@takeExamBp.route('/exam_initialization', methods=['GET', 'POST'])
def exam_initialization():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('takeExamBp.exam_search'))

    exam = Exams.query.get({"exam_id":exam_id})
    if not exam:
        session.pop('exam_id', None)
        return redirect(url_for('takeExamBp.exam_search'))

    exam_instructor = Instructors.query.filter_by(email=exam.instructor_email).first()
    form = ExamInitializationForm()
    if form.validate_on_submit():
        return redirect(url_for('takeExamBp.start'))

    return render_template('exam_initialization.html', form=form, exam=exam, instructor_name=exam_instructor.name)

# Show exam questions
@takeExamBp.route('/start', methods=['GET', 'POST'])
def start():
    exam_id = session.get('exam_id')
    if not exam_id:
        return redirect(url_for('takeExamBp.exam_search'))

    exam = Exams.query.get({"exam_id":exam_id})
    if not exam:
        session.pop('exam_id', None)
        return redirect(url_for('takeExamBp.exam_search'))

    form = SubmissionForm()
    questions = Questions.query.filter_by(exam_id=exam.exam_id).all()

    # Populate the dynamic form with questions
    for index, question in enumerate(questions):
        # Append new question subform if needed
        if index >= len(form.questions):
            form.questions.append_entry()

        subform = form.questions[index]
        subform.question_id.data = question.question_id
        options = Options.query.filter_by(question_id=question.question_id).all()
        choices = [(int(opt.option_id), opt.option_text) for opt in options]

        if question.is_multiple_correct:
            subform.single_or_multi.data = 'multi'
            subform.answer_multi.choices = choices
        else:
            subform.single_or_multi.data = 'single'
            subform.answer_single.choices = choices

        print ("Added question", question.question_id, "with choices", choices)

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

    return render_template('submission.html', form=form, exam=exam, questions=questions)
