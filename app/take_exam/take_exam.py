"""
U5: Exam Taking

This module provides the functionality for students to search for, and take
examinations created by instructors within the Online Examination System (OES).

Functionalities:
- Exam search: Allows students to look up exams by ID.
- Exam initialization: Aalidates exam availability, handles ongoing submissions,
  and sets up a new submission session.
- Exam taking: Presents questions in the in the order the given by the instructor,
  or in a randomzied one, allows student to submit or save and exit.
- Autosave functionality: Periodically saves in-progress submissions to the database.
- Submission finalization: Automatically grades the submission, and updates its relevant
  information in the database

Blueprint:
- `take_examBp` handles all exam-related routes under the URL prefix `/take_exam`.

Dependencies:
- Flask and Flask-Login for web routing, session management, and user authentication.
- SQLAlchemy ORM models for interacting with the database.
- Python standard libraries for date/time handling and platform-specific adjustments.
"""

# Third-party imports
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

# Built-in Python imports
import platform
import random
from datetime import datetime
from zoneinfo import ZoneInfo

# Local Imports
from app.take_exam.forms import ExamSearchForm, ExamInitializationForm, SubmissionForm
from app.models import db, Instructors, Exams, Questions, Options, Submissions

# Instantiate blueprint
take_examBp = Blueprint("take_examBp", __name__, url_prefix="/take_exam",  template_folder="templates")

# Helper function
def finalize_submission(submission, answers, questions):
    """
    - Calculation submission score
    - Sets score, time of submission, and changes status
    - Updates database
    """

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
        if option and option.is_correct:
            score += question.points

    submission.total_score = score
    submission.submitted_at = datetime.utcnow()
    submission.status = "SUBMITTED"

    print(f"[U5] Submitted {submission.submission_id} with answers {answers}") # Debugging


##### User-Accessible Routes #####
@take_examBp.route('', methods=['GET', 'POST'])
@login_required
def exam_search():
    # Check if the user is a student
    try:
        submission = Submissions.query.filter_by(roll_number=current_user.roll_number, status="IN_PROGRESS").first()
    except Exception:
        flash('Instructors cannot access the requested page', 'danger')
        return redirect(url_for('dashboard'))

    # Check for unfinished submission using the DB, and update cookies if there's one
    if submission:
        session['current_exam_id'] = submission.exam_id
        session['current_submission_id'] = submission.submission_id
        print("[U5] Student has unfinished submission") # Debugging
        return redirect(url_for('take_examBp.initialization'))

    form = ExamSearchForm()
    if form.validate_on_submit():
        exam = Exams.query.get(form.examID.data)

        # Save searched-for exam
        session['current_exam_id'] = exam.exam_id
        return redirect(url_for('take_examBp.initialization'))

    return render_template('exam_search.html', form=form)


@take_examBp.route('/initialization', methods=['GET', 'POST'])
@login_required
def initialization():
    # Validate exam cookie
    current_exam_id = session.get('current_exam_id')
    if not current_exam_id:
        return redirect(url_for('take_examBp.exam_search'))

    exam = Exams.query.get(current_exam_id)
    if not exam:
        session.pop('current_exam_id', None)
        return redirect(url_for('take_examBp.exam_search'))

    # Check if student has an unfinished submission
    taking_exam = False
    current_submission_id = session.get('current_submission_id')
    if current_submission_id:
        submission = Submissions.query.get(current_submission_id)
        if (not submission) or (submission and submission.status != "IN_PROGRESS"):
            session.pop('current_submission_id', None)
        else:
            # If there's an active submission but the exam and
            # submission cookies don't match, the exam cookie must be updated
            if submission.exam_id != current_exam_id:
                current_exam_id = submission.exam_id
                session['current_exam_id'] = submission.exam_id

            taking_exam = True

    # Check exam availability
    exam_open = True
    current_datetime = datetime.utcnow()
    if current_datetime < exam.opens_at or current_datetime > exam.closes_at:
        exam_open = False

    exam_instructor = Instructors.query.filter_by(email=exam.instructor_email).first()

    if platform.system() == 'Darwin':
        local_tz = None
    else:
        try:
            local_tz = ZoneInfo("localtime")
        except Exception:
            local_tz = None

    local_tz_availability = [exam.opens_at.astimezone(local_tz), exam.closes_at.astimezone(local_tz)]

    form = ExamInitializationForm()
    form.exam_id.data = current_exam_id
    if form.validate_on_submit():
        if form.continue_submission.data:
            return redirect(url_for('take_examBp.start'))

        if form.cancel.data:
            # Remove the exam cookie if user declines to start exam
            session.pop('current_exam_id', None)
            return redirect(url_for('take_examBp.exam_search'))

        # Initialize submission and store it in the database + as a cookie
        submission = Submissions(
            exam_id = exam.exam_id,
            roll_number = current_user.roll_number,
            started_at = current_datetime,
            status = "IN_PROGRESS"
        )
        db.session.add(submission)
        db.session.commit()
        session['current_submission_id'] = submission.submission_id

        return redirect(url_for('take_examBp.start'))

    return render_template('exam_initialization.html', form=form, exam=exam, instructor=exam_instructor,
        taking_exam=taking_exam, exam_open=exam_open, availability=local_tz_availability)


@take_examBp.route('/start', methods=['GET', 'POST'])
@login_required
def start():
    # Validate exam cookie
    current_exam_id = session.get('current_exam_id')
    if not current_exam_id:
        return redirect(url_for('take_examBp.exam_search'))

    exam = Exams.query.get(current_exam_id)
    if not exam:
        session.pop('current_exam_id', None)
        return redirect(url_for('take_examBp.exam_search'))

    # Validate submission cookie
    current_submission_id = session.get('current_submission_id')
    if not current_submission_id:
        return redirect(url_for('take_examBp.initialization'))

    submission = Submissions.query.get(current_submission_id)
    if (not submission):
        session.pop('current_submission_id', None)
        return redirect(url_for('take_examBp.initialization'))

    is_post = request.method == 'POST'
    if not is_post:
        questions = Questions.query.filter_by(exam_id=exam.exam_id).order_by(Questions.order_index.asc()).all()

        # Shuffle on GET
        if exam.security_settings["shuffle"]:
            random.shuffle(questions)

        # Save shuffle order
        session["shuffled_order"] = [q.question_id for q in questions]
    else:
        # DO NOT reshuffle order on POST
        ordered_ids = session.get('shuffled_order')
        questions = Questions.query.filter(Questions.question_id.in_(ordered_ids)).all()

        questions.sort(key=lambda q: ordered_ids.index(q.question_id))

    # Retrieve saved answers, if any, in the correct dict format
    # Eg. {'5': 14, '6': [16, 17, 18]} --> {5: 14, 6: [16, 17, 18]}
    saved_answers = submission.answers or {}
    saved_answers = {int(k): v for k, v in saved_answers.items()}

    form = SubmissionForm()

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

            # Load saved answers on the submission from the DB, ONLY if it's not a POST request,
            # otherwise it'll overwrite any changes every time
            if not is_post and question.question_id in saved_answers:
                subform.answer_multi.data = saved_answers[question.question_id]

        else:
            subform.single_or_multi.data = 'single'
            subform.answer_single.choices = choices

            if not is_post and question.question_id in saved_answers:
                subform.answer_single.data = saved_answers[question.question_id]

        print(f"[U5] Added question {question.question_id} with choices {choices}") # Debugging


    if form.validate_on_submit():
        print("[U5] Submission form validated") # Debugging

        # Once a student submits they can't change their submission, only start a new one
        if submission.status != "IN_PROGRESS":
            return redirect(url_for('dashboard'))

        # Collect answers
        answers = {}
        for subform in form.questions:
            qid = subform.question_id.data

            if subform.single_or_multi.data == 'multi':
                answers[qid] = subform.answer_multi.data
            else:
                answers[qid] = subform.answer_single.data

        print(f"[U5] Collected answers: {answers}") # Debugging

        submission.answers = answers
        submission.updated_at = datetime.utcnow()

        if (form.submit.data):
            finalize_submission(submission, answers, questions)

        session.pop('current_submission_id', None)
        session.pop('current_exam_id', None)
        session.pop('shuffled_order', None)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template(
        'submission.html', form=form, exam=exam, questions=questions,
        remaining_seconds=int((exam.closes_at - datetime.utcnow()).total_seconds())
    )


##### User-Innacessible Route #####
@take_examBp.route("/autosave", methods=["POST"])
@login_required
def autosave():
    submission_id = session.get("current_submission_id")
    if not submission_id:
        return ("no submission", 400)

    submission = Submissions.query.get(submission_id)
    if not submission or submission.status != "IN_PROGRESS":
        return ("invalid", 400)

    form = SubmissionForm()
    answers = {}

    for subform in form.questions:
        qid = subform.question_id.data
        if subform.single_or_multi.data == "multi":
            answers[qid] = subform.answer_multi.data
        else:
            answers[qid] = subform.answer_single.data

    submission.answers = answers
    submission.updated_at = datetime.utcnow()
    db.session.commit()
    return ("ok", 200)
