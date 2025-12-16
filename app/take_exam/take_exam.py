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
import random
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Local Imports
from app.take_exam.forms import ExamSearchForm, ExamInitializationForm, SubmissionForm
from app.models import db, Instructors, Exams, Questions, Options, Submissions

# Instantiate blueprint
take_examBp = Blueprint("take_examBp", __name__, url_prefix="/take_exam",  template_folder="templates")

# Helper function
def finalize_submission(submission, answers, questions):
    """
    - Calculates submission score
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

    # If the student has an unfinished submission don't let them search for an exam
    if submission:
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
    submission = Submissions.query.filter_by(roll_number=current_user.roll_number, status="IN_PROGRESS").first()
    current_datetime = datetime.utcnow()
    started_exam = False
    taking_exam_now = False

    # Check if there's an unfinished submission
    if submission:
        started_exam = True
        current_exam_id = submission.exam_id
        session['current_exam_id'] = submission.exam_id

        # If the latest update was within the autosave window, it means the student
        # is currently taking the exam on another browser tab (already has a session)
        # TODO: Replace magic number(autosave interval + small grace period to account for autosave delays)
        #       with proper const variables that are set in .conf
        taking_exam_now = (int((current_datetime - submission.updated_at).total_seconds()) <= 7)
    else:
        # Validate the cookie that was set in exam search
        current_exam_id = session.get('current_exam_id')
        if not current_exam_id:
            return redirect(url_for('take_examBp.exam_search'))

    # Check if exam actually exists
    exam = Exams.query.get(current_exam_id)
    if not exam:
        session.pop('current_exam_id', None)
        session.pop('current_submission_id', None) #PROBABLY NOT NEEDED
        return redirect(url_for('take_examBp.exam_search'))

    # If the exam allows only single sessions and they're already taking it, they can't open it in another window
    single_session = exam.security_settings['single_session']
    if single_session and taking_exam_now:
        flash('Only a single session per student is allowed for the active exam, and it is already open in another browser tab.', 'warning')
        return redirect(url_for('dashboard'))

    exam_instructor = Instructors.query.filter_by(email=exam.instructor_email).first()
    exam_open = (exam.opens_at < current_datetime and current_datetime < exam.closes_at)

    # Make open and close datetimes timezone aware to display them properly in the student's timezone
    tz_aware_dates = [exam.opens_at.replace(tzinfo=ZoneInfo("UTC")), exam.closes_at.replace(tzinfo=ZoneInfo("UTC"))]
    print(f"[U5] Exam window: {tz_aware_dates[0]} until {tz_aware_dates[1]}")

    form = ExamInitializationForm()
    form.exam_id.data = current_exam_id
    if form.validate_on_submit():
        if form.cancel.data:
            # Remove the exam cookie if user declines to start exam
            session.pop('current_exam_id', None)
            return redirect(url_for('take_examBp.exam_search'))

        if form.accept.data:
            # Initialize submission and store it in the database + as a cookie
            current_datetime = datetime.utcnow()
            submission = Submissions(
                exam_id = exam.exam_id,
                roll_number = current_user.roll_number,
                started_at = current_datetime,
                updated_at = current_datetime,
                status = "IN_PROGRESS"
            )
            db.session.add(submission)
            db.session.commit()

        # Cookies that act as one-time tokens are required to start/continue single-session exams
        if single_session:
            session['can_start'] = True

        session['current_submission_id'] = submission.submission_id
        return redirect(url_for('take_examBp.start'))

    return render_template('exam_initialization.html', form=form, exam=exam, instructor=exam_instructor,
        started_exam=started_exam, exam_open=exam_open, availability=tz_aware_dates)


@take_examBp.route('/start', methods=['GET', 'POST'])
@login_required
def start():
    # Validate submission cookie
    current_submission_id = session.get('current_submission_id')
    if not current_submission_id:
        return redirect(url_for('take_examBp.initialization'))

    submission = Submissions.query.get(current_submission_id)
    if not submission or submission.status != "IN_PROGRESS":
        session.pop('current_submission_id', None)
        return redirect(url_for('take_examBp.initialization'))

    # Validate exam cookie
    current_exam_id = session.get('current_exam_id')
    if current_exam_id != submission.exam_id:
        current_exam_id = submission.exam_id
        session['current_exam_id'] = submission.exam_id

    exam = Exams.query.get(current_exam_id)
    if not exam:
        session.pop('current_exam_id', None)
        session.pop('current_submission_id', None)
        return redirect(url_for('take_examBp.exam_search'))

    is_post = request.method == 'POST'
    if not is_post:
        # If the exam is single-session and the user doesn't have the required token, kick them out
        if exam.security_settings['single_session']:
            if not session.get('can_start'):
                return redirect(url_for('take_examBp.initialization'))

            # Consume the start token and give them another token that allows saving or submitting
            session.pop('can_start', None)
            session['can_save_or_sub'] = True

        # Retrive the exams questions in order
        questions = Questions.query.filter_by(exam_id=exam.exam_id).order_by(Questions.order_index.asc()).all()

        # Shuffle order if the setting is enabled
        if exam.security_settings["shuffle"]:
            random.shuffle(questions)

        # Save order to use when saving or submitting
        session["shuffled_order"] = [q.question_id for q in questions]
    else:
        # Retreive question order used on page load
        ordered_ids = session.get('shuffled_order')
        if not ordered_ids:
            flash('Correct question order unknown. Saving/Submitting failed.', 'danger')
            return redirect(url_for('initialization'))

        questions = Questions.query.filter(Questions.question_id.in_(ordered_ids)).all()
        questions.sort(key=lambda q: ordered_ids.index(q.question_id))

    # Retrieve saved answers, if any, and convert them to the correct dict format
    # (keys must be ints, e.g., {'5': 14, '6': [16, 17, 18]} --> {5: 14, 6: [16, 17, 18]})
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

        # PROBABLY NOT NEEDED
        if submission.status != "IN_PROGRESS":
            return redirect(url_for('dashboard'))

        # Student's need a token to save or submit in single-session mode
        if exam.security_settings['single_session'] and not session.get('can_save_or_sub'):
            return redirect(url_for('take_examBp.initialization'))

        # Collect answers
        answers = {}
        for subform in form.questions:
            qid = subform.question_id.data

            if subform.single_or_multi.data == 'multi':
                answers[qid] = subform.answer_multi.data
            else:
                answers[qid] = subform.answer_single.data

        print(f"[U5] Collected answers {answers} for submission {current_submission_id}") # Debugging

        submission.answers = answers
        submission.updated_at = datetime.utcnow()

        if (form.submit_flag.data == "1"):
            finalize_submission(submission, answers, questions)

        session.pop('current_submission_id', None)
        session.pop('current_exam_id', None)
        session.pop('shuffled_order', None)
        session.pop('can_save_or_sub', None)
        db.session.commit()

        return redirect(url_for('dashboard'))

    return render_template(
        'submission.html', form=form, exam=exam, questions=questions, feedback=submission.feedback,
        remaining_seconds=int((exam.closes_at - datetime.utcnow()).total_seconds())
    )


##### User-Innacessible Endpoint #####
@take_examBp.route("/autosave", methods=["POST"])
@login_required
def autosave():
    submission_id = session.get("current_submission_id")
    if not submission_id:
        return ("no active submission", 400)

    submission = Submissions.query.get(submission_id)
    if not submission or submission.status != "IN_PROGRESS":
        return ("invalid submission", 400)

    save_type = request.form.get("autosave_type")

    if save_type == "progress":
        form = SubmissionForm()
        answers = {}

        for subform in form.questions:
            qid = subform.question_id.data
            if subform.single_or_multi.data == "multi":
                answers[qid] = subform.answer_multi.data
            else:
                answers[qid] = subform.answer_single.data

        submission.answers = answers
    elif save_type == "report":
        feedback = request.form.get("feedback")

        if feedback:
            submission.feedback = feedback
        else:
            return ("missing report feedback", 400)
    else:
        return ("unknown autosave type", 400)

    submission.updated_at = datetime.utcnow()
    db.session.commit()
    print(f"[U5] Autosaved {save_type} for submission {submission_id}")
    return ("autosaved", 200)
