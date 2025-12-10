# Built-in Python import
from datetime import datetime, timezone

# Local Imports
from app import app, scheduler, db
from app.models import Exams, Questions, Submissions
from app.take_exam.take_exam import finalize_submission

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
    - Schedules one Celery task per active exam to run at the exam's closing time
    """
    with app.app_context():
        # Get currently active exams
        now = datetime.utcnow()
        active_exams = Exams.query.filter(
            Exams.opens_at <= now,
            Exams.closes_at > now
        ).all()

        # Schedule a single task per active exam
        for exam in active_exams:
            # Check if the detected exam already has a timer
            job_id = f"close_{exam.exam_id}"
            job = scheduler.get_job(job_id)
            if job:
                if job.next_run_time == exam.closes_at.replace(tzinfo=timezone.utc):
                    continue
                scheduler.remove_job(job_id)

            remaining_time = (exam.closes_at - now).total_seconds()
            if remaining_time > 0:
                scheduler.add_job(
                    id=job_id,
                    func=close_exam,
                    args=[exam.exam_id],
                    trigger="date",
                    run_date=exam.closes_at
                )
                print(f"[Scheduler] Timer scheduled for Exam {exam.exam_id} at {exam.closes_at}(UTC)")
