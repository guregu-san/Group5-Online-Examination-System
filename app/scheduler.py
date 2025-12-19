# Built-in Python import
from datetime import datetime, timezone, timedelta
import os

# Local Imports
from app import app, scheduler, db
from app.models import Exams, Questions, Submissions
from app.take_exam.take_exam import finalize_submission

AUTOSAVE_GRACE_PERIOD=int(os.getenv('AUTOSAVE_GRACE_PERIOD'))

def close_exam(exam_id):
    """
    APScheduler job that runs once at the closing time of an exam.
    - Finds all submissions for the given exam that are currently in progress
    - Finalizes the submissions and updates the database
    """
    with app.app_context():
        exam = Exams.query.get(exam_id)
        if exam:
            print(f"[Scheduler] Exam {exam_id} expired.")
            active_submissions = Submissions.query.filter_by(exam_id=exam_id, status="IN_PROGRESS").all()

            for submission in active_submissions:
                saved_answers = submission.answers or {}
                saved_answers = {int(k): v for k, v in saved_answers.items()}
                questions = Questions.query.filter_by(exam_id=exam_id)
                finalize_submission(submission, saved_answers, questions)

                db.session.commit()
                print(f"[Scheduler] Autosubmited {submission.submission_id}.")

def set_exam_timers():
    """
    APScheduler job that runs every minute.
    - Finds all exams that are currently active (opened but not yet closed)
    - Schedules one job per active exam to run at the exam's closing time
    """
    with app.app_context():
        # Get currently active exams
        now = datetime.utcnow()
        active_exams = Exams.query.filter(
            Exams.opens_at <= now,
            Exams.closes_at > now
        ).all()

        for exam in active_exams:
            job_id = f"close_{exam.exam_id}"
            job = scheduler.get_job(job_id)

            # Added delay so autosave will have time to run one last time on exam expiration
            expiration = exam.closes_at + timedelta(seconds=AUTOSAVE_GRACE_PERIOD)

            # If the exam doesn't already have a timer, set one,
            # or if it has one but it doesn't match with the close time update it
            if job:
                # Expiration time needs to be timezone-aware for the comparison
                if job.next_run_time == expiration.replace(tzinfo=timezone.utc):
                    continue
                scheduler.remove_job(job_id)

            if (exam.closes_at - now).total_seconds() > 0:
                scheduler.add_job(
                    id=job_id,
                    func=close_exam,
                    args=[exam.exam_id],
                    trigger="date",
                    run_date=expiration
                )
                print(f"[Scheduler] Expiration scheduled for Exam {exam.exam_id} at {expiration}(UTC)")
