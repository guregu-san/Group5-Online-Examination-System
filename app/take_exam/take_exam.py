import sqlite3
import json
from flask import Blueprint, render_template, redirect, url_for, jsonify, request, session
from flask_login import login_required, current_user
from datetime import datetime

from app.take_exam.forms import ExamSearchForm, ExamInitializationForm, SubmissionForm
from app.models import db, Students, Instructors, Courses, Exams, Questions, Options, Submissions

takeExamBp = Blueprint("takeExamBp", __name__, url_prefix="/take_exam",  template_folder="templates")

'''Routes'''
# Find the exam
# TODO: Make endpoints accessible ONLY to logged-in students
@takeExamBp.route('', methods=['GET', 'POST'])
def exam_search():
    form = ExamSearchForm()
    if form.validate_on_submit():
        exam = Exams.query.get(form.examID.data)

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
    form.exam_id.data = exam_id
    if form.validate_on_submit():
        submission = Submissions(
            exam_id = exam.exam_id,
            roll_number = current_user.roll_number,
            started_at = datetime.utcnow(),
            status = "IN_PROGRESS"
        )
        db.session.add(submission)
        db.session.commit()

        return redirect(url_for('takeExamBp.start'))

    return render_template('exam_initialization.html', form=form, exam=exam, instructor_name=exam_instructor.name)

# Show exam questions
# TODO: Add save and exit functionality + create submission as soon as student starts exam
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

        print ("Added question", question.question_id, "with choices", choices) # Debugging

    if form.validate_on_submit():
        # Collect answers
        answers = {}
        print ("Submission validated") # Debugging
        for subform in form.questions:
            qid = subform.question_id.data

            if subform.single_or_multi.data == 'multi':
                answers[qid] = subform.answer_multi.data
            else:
                answers[qid] = subform.answer_single.data

        print("Collected answers:", answers) # Debugging


        submission = Submissions.query.filter_by(exam_id=exam.exam_id, roll_number=current_user.roll_number).order_by(Submissions.started_at.desc()).first()

        if (submission.status != "IN_PROGRESS"):
            return redirect(url_for('dashboard'))

        submission.answers = answers
        submission.updated_at = datetime.utcnow()

        if (form.submit.data):
            # Calculate score
            score = 0
            for question in questions:
                if question.is_multiple_correct:
                    answers_are_correct = True
                    correct_options = Options.query.filter_by(question_id=question.question_id, is_correct=True).all()
                    for option in correct_options:
                        if option.option_id not in answers[question.question_id]:
                            answers_are_correct = False

                    if answers_are_correct:
                        score += question.points

                    continue

                option = Options.query.get(answers[question.question_id])
                if option.is_correct:
                    score += question.points

            submission.submitted_at = datetime.utcnow()
            submission.status = "SUBMITTED"
            submission.total_score = score
            print("Exam submitted: ", answers) # Debugging

        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template('submission.html', form=form, exam=exam, questions=questions)
