import unittest
from unittest.mock import patch
import os
from datetime import datetime, timedelta

from app import app, db, bcrypt
from app.models import Courses, Students, Instructors, Exams, Questions, Options, Submissions
from app.scheduler import close_exam

ACTIVE_EXAM_CHECK_INTERVAL = int(os.getenv('ACTIVE_EXAM_CHECK_INTERVAL'))

class TestExamTakingUseCase(unittest.TestCase):
    def setUp(self):
        # Configure test app
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        # Simulate a web browser
        self.client = app.test_client()

        # Give app context and activate it
        self.ctx = app.app_context()
        self.ctx.push()

        # Rebuild DB
        db.drop_all()
        db.create_all()

        # Sample instructor
        self.instructor = Instructors(
            name="John Carmack", email="jcar@idsoftware.com",
            password_hash=bcrypt.generate_password_hash('doom1993').decode('utf-8')
        )
        db.session.add(self.instructor)
        db.session.commit()

        # Sample student
        self.student = Students(
            roll_number=1, name="John Romero", email="jrom@idsoftware.com",
            password_hash=bcrypt.generate_password_hash('doom1993').decode('utf-8')
        )
        db.session.add(self.student)
        db.session.commit()

        # Sample course
        self.course = Courses(
            course_code="CS101", course_name="Example Course",
            instructor_email="jcar@idsoftware.com"
        )
        db.session.add(self.course)
        db.session.commit()

        now = datetime.utcnow()

        # Sample exam
        self.exam = Exams(
            instructor_email=self.instructor.email,
            title="Sample Exam",
            course_code="CS101",
            security_settings={"password": "", "shuffle": False, "single_session": False, "no_tab_switching": False},
            opens_at=now - timedelta(hours=1),
            closes_at=now + timedelta(hours=1),
            created_at=now
        )
        db.session.add(self.exam)
        db.session.commit()

        # Add questions and options for protected exam
        self.q1 = Questions(exam_id=self.exam.exam_id, question_text="Q1?", is_multiple_correct=False, points=5, order_index=1)
        self.q2 = Questions(exam_id=self.exam.exam_id, question_text="Q2?", is_multiple_correct=True, points=10, order_index=2)
        db.session.add_all([self.q1, self.q2])
        db.session.commit()

        self.q1_op1 = Options(question_id=self.q1.question_id, option_text="Correct", is_correct=True)
        self.q1_op2 = Options(question_id=self.q1.question_id, option_text="Wrong", is_correct=False)
        self.q2_op1 = Options(question_id=self.q2.question_id, option_text="Correct", is_correct=True)
        self.q2_op2 = Options(question_id=self.q2.question_id, option_text="Wrong", is_correct=False)
        self.q2_op3 = Options(question_id=self.q2.question_id, option_text="Correct", is_correct=True)
        db.session.add_all([self.q1_op1, self.q1_op2, self.q2_op1, self.q2_op2, self.q2_op3])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()


    ########## Login Helper ##########
    def login_student(self):
        patcher = patch('flask_login.utils._get_user', return_value=self.student)
        self.addCleanup(patcher.stop)
        patcher.start()


    ########## Test Cases ##########
    # U5-TC1: Valid exam search
    def test_search_valid_exam(self):
        self.login_student()
        response = self.client.post(
            "/take_exam",
            data={"examID": self.exam.exam_id},
            follow_redirects=True
        )

        self.assertIn(b"Accept", response.data)

    # U5-TC2: Invalid exam search
    def test_search_invalid_exam(self):
        self.login_student()
        response = self.client.post(
            "/take_exam",
            data={"examID": 5},
            follow_redirects=True
        )

        # Make sure the popup shows up and that the student stays on the search page
        self.assertIn(b"Exam not found", response.data)
        self.assertIn(b"Exam Search", response.data)

    # U5-TC3: Searching for a currently unavailable exam
    def test__search_unavailable_exam(self):
        self.login_student()
        self.exam.closes_at = datetime.utcnow() - timedelta(hours=1)

        response = self.client.post(
            "/take_exam",
            data={"examID": self.exam.exam_id},
            follow_redirects=True
        )

        self.assertIn(b"Exam is currently unavailable", response.data)

    # U5-TC4: Condition acceptance (not password protected)
    def test_accept_conditions_unprotected(self):
        self.login_student()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        response = self.client.post(
            "/take_exam/initialization",
            data={"accept": True},
            follow_redirects=True
        )

        submission = Submissions.query.filter_by(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number
        ).first()

        self.assertIsNotNone(submission)
        self.assertEqual(submission.status, "IN_PROGRESS")
        self.assertIn(b"Time Left", response.data)

    # U5-TC5: Successful condition acceptance on password protected exam
    def test_accept_conditions_valid_password(self):
        self.login_student()
        password = "pass1234"
        settings = dict(self.exam.security_settings)
        settings["password"] = password
        self.exam.security_settings = settings
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        response = self.client.post(
            "/take_exam/initialization",
            data={"password": password, "accept": True},
            follow_redirects=True
        )

        submission = Submissions.query.filter_by(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number,
            status="IN_PROGRESS"
        ).first()

        self.assertIsNotNone(submission)
        self.assertIn(b"Time Left", response.data)

    # U5-TC6: Unsuccessful condition acceptance on password protected exam
    def test_accept_conditions_invalid_password(self):
        self.login_student()
        settings = dict(self.exam.security_settings)
        settings["password"] = "pass1234"
        self.exam.security_settings = settings
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        response = self.client.post(
            "/take_exam/initialization",
            data={"password": "pass", "accept": True},
            follow_redirects=True
        )

        submission = Submissions.query.filter_by(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number,
            status="IN_PROGRESS"
        ).first()

        self.assertIsNone(submission)
        self.assertIn(b"Wrong password", response.data)
        self.assertIn(b"Sample Exam", response.data)

    # U5-TC7: Declining exam conditions
    def test_decline_conditions(self):
        self.login_student()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        response = self.client.post(
            "/take_exam/initialization",
            data={"cancel": True},
            follow_redirects=True
        )

        self.assertIn(b"Exam Search", response.data)

    # U5-TC8: Save and exit mid-exam
    def test_save_and_exit(self):
        self.login_student()

        now = datetime.utcnow()
        submission = Submissions(
            exam_id = self.exam.exam_id,
            roll_number = self.student.roll_number,
            started_at = now - timedelta(minutes=5),
            updated_at = now - timedelta(minutes=5),
            status = "IN_PROGRESS"
        )
        db.session.add(submission)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["current_submission_id"] = submission.submission_id
            sess["current_exam_id"] = self.exam.exam_id
            sess["shuffled_order"] = [
                self.q1.question_id,
                self.q2.question_id
            ]

        answers = {
            "questions-0-question_id": self.q1.question_id,
            "questions-0-single_or_multi": "single",
            "questions-0-answer_single": self.q1_op1.option_id,

            "questions-1-question_id": self.q2.question_id,
            "questions-1-single_or_multi": "multi",
            "questions-1-answer_multi": [
                self.q2_op1.option_id,
                self.q2_op3.option_id
            ],
        }

        response = self.client.post(
            "/take_exam/start",
            data=answers,
            follow_redirects=True
        )

        submission = Submissions.query.get(submission.submission_id)

        self.assertIsNotNone(submission)
        self.assertEqual(submission.status, "IN_PROGRESS")
        self.assertIsNotNone(submission.answers)
        self.assertIn(b"Welcome", response.data)

    # U5-TC9: Resume saved exam
    def test_resume_exam(self):
        self.login_student()

        now = datetime.utcnow()
        submission = Submissions(
            exam_id = self.exam.exam_id,
            roll_number = self.student.roll_number,
            started_at = now - timedelta(minutes=10),
            updated_at = now - timedelta(minutes=5),
            status = "IN_PROGRESS",
            answers = {
                str(self.q1.question_id): self.q1_op1.option_id,
                str(self.q2.question_id): [
                    self.q2_op1.option_id,
                    self.q2_op3.option_id
                ]
            }
        )
        db.session.add(submission)
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        # Student tries to go to the search page
        response = self.client.get(
            "/take_exam",
            follow_redirects=True
        )

        self.assertIn(b"Continue", response.data)

        response = self.client.post(
            "/take_exam/initialization",
            data={"continue_submission": True},
            follow_redirects=True
        )

        submission = Submissions.query.filter_by(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number
        ).first()

        # Make sure the submission is still in progress, and that the selected answers were saved
        self.assertIsNotNone(submission)
        self.assertEqual(submission.status, "IN_PROGRESS")
        self.assertEqual(submission.answers[str(self.q1.question_id)], self.q1_op1.option_id)
        self.assertEqual(submission.answers[str(self.q2.question_id)], [
            self.q2_op1.option_id,
            self.q2_op3.option_id
        ])
        self.assertIn(b"Time Left", response.data)

    # U5-TC10: Manual submission
    def test_manual_submission(self):
        self.login_student()

        now = datetime.utcnow()
        submission = Submissions(
            exam_id = self.exam.exam_id,
            roll_number = self.student.roll_number,
            started_at = now - timedelta(minutes=5),
            updated_at = now - timedelta(minutes=5),
            status = "IN_PROGRESS"
        )
        db.session.add(submission)
        db.session.commit()
        self.exam.closes_at = datetime.utcnow() - timedelta(hours=1)

        with self.client.session_transaction() as sess:
            sess["current_submission_id"] = submission.submission_id
            sess["current_exam_id"] = self.exam.exam_id
            sess["shuffled_order"] = [
                self.q1.question_id,
                self.q2.question_id
            ]

        answers = {
            "questions-0-question_id": self.q1.question_id,
            "questions-0-single_or_multi": "single",
            "questions-0-answer_single": self.q1_op1.option_id,

            "questions-1-question_id": self.q2.question_id,
            "questions-1-single_or_multi": "multi",
            "questions-1-answer_multi": [
                self.q2_op1.option_id,
                self.q2_op3.option_id
            ],

            "submit_flag": "1"
        }

        response = self.client.post(
            "/take_exam/start",
            data=answers,
            follow_redirects=True
        )

        submission = Submissions.query.get(submission.submission_id)

        self.assertIsNotNone(submission)
        self.assertIsNotNone(submission.submitted_at)
        self.assertEqual(submission.status, "SUBMITTED")
        self.assertEqual(submission.total_score, (self.q1.points + self.q2.points))
        self.assertIn(b"Submitted successfully!", response.data)
        self.assertIn(b"Welcome", response.data)

    # U5-TC11: Exam retry
    def test_exam_retry(self):
        self.login_student()

        now = datetime.utcnow()
        submission = Submissions(
            exam_id = self.exam.exam_id,
            roll_number = self.student.roll_number,
            started_at = now - timedelta(minutes=10),
            updated_at = now - timedelta(minutes=5),
            submitted_at = now - timedelta(minutes=5),
            status = "SUBMITTED",
            answers = {
                str(self.q1.question_id): self.q1_op1.option_id,
                str(self.q2.question_id): [
                    self.q2_op1.option_id,
                    self.q2_op3.option_id
                ]
            },
            total_score = (self.q1.points + self.q2.points)
        )
        db.session.add(submission)
        db.session.commit()

        response = self.client.post(
            "/take_exam",
            data={"examID": self.exam.exam_id},
            follow_redirects=True
        )

        self.assertIn(b"Accept", response.data)

        response = self.client.post(
            "/take_exam/initialization",
            data={"accept": True},
            follow_redirects=True
        )

        submissions = Submissions.query.filter_by(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number
        ).order_by(Submissions.submission_id.asc()).all()

        self.assertEqual(len(submissions), 2)
        self.assertEqual(submissions[1].status, "IN_PROGRESS")
        self.assertIn(b"Time Left", response.data)

    # U5-TC12: Timer runs out during exam
    def test_exam_expiration(self):
        self.login_student()

        now = datetime.utcnow()
        submission = Submissions(
            exam_id = self.exam.exam_id,
            roll_number = self.student.roll_number,
            started_at = now - timedelta(minutes=10),
            updated_at = now - timedelta(minutes=5),
            status = "IN_PROGRESS",
            answers = {
                str(self.q1.question_id): self.q1_op1.option_id,
                str(self.q2.question_id): [
                    self.q2_op1.option_id,
                    self.q2_op3.option_id
                ]
            }
        )
        db.session.add(submission)
        db.session.commit()

        self.exam.closes_at = datetime.utcnow()
        db.session.commit()

        # Close exam manually (normally done by our beautiful scheduler)
        close_exam(self.exam.exam_id)

        response = self.client.post(
            "/take_exam",
            data={"examID": self.exam.exam_id},
            follow_redirects=True
        )

        self.assertIn(b"Exam is currently unavailable", response.data)

        submission = Submissions.query.get(submission.submission_id)

        self.assertIsNotNone(submission)
        self.assertIsNotNone(submission.submitted_at)
        self.assertEqual(submission.status, "SUBMITTED")
        self.assertEqual(submission.total_score, (self.q1.points + self.q2.points))

    # U5-TC13: Question order randomization
    def test_question_shuffling(self):
        self.login_student()

        settings = dict(self.exam.security_settings)
        settings["shuffle"] = True
        self.exam.security_settings = settings
        db.session.commit()

        with self.client.session_transaction() as sess:
            sess["current_exam_id"] = self.exam.exam_id

        response = self.client.post(
            "/take_exam/initialization",
            data={"accept": True},
            follow_redirects=True
        )

        self.assertIn(b"Time Left", response.data)

        with self.client.session_transaction() as sess:
            order = sess.get("shuffled_order")

        # I KNOW IT'S NOT DETERMINISTIC BUT THE CHANCE TO FAIL DUE TO UNLUCKY STREAK IS IMPOSSIBLY LOW
        original_order = [self.q1.question_id, self.q2.question_id]
        max_attempts = 30
        attempt = 0
        while order == original_order and attempt < max_attempts:
            attempt += 1
            with self.client.session_transaction() as sess:
                    sess.pop("shuffled_order", None)

            response = self.client.get(
                "/take_exam/start",
                follow_redirects=True
            )
            self.assertIn(b"Time Left", response.data)

            with self.client.session_transaction() as sess:
                order = sess.get("shuffled_order")

        self.assertIn(b"Time Left", response.data)
        self.assertNotEqual(order, original_order)

    # U5-TC14: Single session exams
    def test_single_session(self):
        self.login_student()
        settings = dict(self.exam.security_settings)
        settings["single_session"] = True
        self.exam.security_settings = settings

        submission = Submissions(
            exam_id=self.exam.exam_id,
            roll_number=self.student.roll_number,
            started_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status="IN_PROGRESS"
        )
        db.session.add(submission)
        db.session.commit()

        # Make sure all endpoints redirect to dashboard and flash the wanrning.
        searchResponse = self.client.get("/take_exam",follow_redirects=True)
        initResponse = self.client.get("/take_exam/initialization",follow_redirects=True)
        startResponse = self.client.get("/take_exam/start",follow_redirects=True)

        self.assertIn(b"Welcome", searchResponse.data)
        self.assertIn(b"Welcome", initResponse.data)
        self.assertIn(b"Welcome", startResponse.data)
        self.assertIn(b"Only a single session per student is allowed", searchResponse.data)
        self.assertIn(b"Only a single session per student is allowed", initResponse.data)
        self.assertIn(b"Only a single session per student is allowed", startResponse.data)

if __name__ == "__main__":
    unittest.main()
