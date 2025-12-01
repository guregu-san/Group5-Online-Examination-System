from flask_login import UserMixin
from sqlalchemy.sql.sqltypes import Enum

from app import db


class Students(db.Model, UserMixin):
    roll_number = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    contact_number = db.Column(db.Integer, unique=True, nullable=True)
    role = "Student"

    def get_id(self):
        return f"student-{self.roll_number}"


class Instructors(db.Model, UserMixin):
    instructor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    role = "Instructor"

    def get_id(self):
        return f"instructor-{self.instructor_id}"


class Courses(db.Model):
    course_code = db.Column(db.String(50), primary_key=True)
    course_name = db.Column(db.String(100), nullable=False)
    instructor_email = db.Column(db.String(50), db.ForeignKey("instructors.email"), nullable=False)


class Exams(db.Model):
    exam_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    instructor_email = db.Column(db.String(50), db.ForeignKey("instructors.email"), nullable=False)
    course_code = db.Column(db.String(50), db.ForeignKey("courses.course_code"))
    title = db.Column(db.String(100), nullable=False)
    time_limit = db.Column(db.Integer, nullable=True)
    security_settings = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime)


class Questions(db.Model):
    question_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.exam_id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    is_multiple_correct = db.Column(db.Boolean, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    order_index = db.Column(db.Integer, nullable=False)


class Options(db.Model):
    option_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.question_id"), nullable=False)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)


class Submissions(db.Model):
    submission_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.exam_id"), nullable=False)
    roll_number = db.Column(db.Integer, db.ForeignKey("students.roll_number"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    submitted_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    feedback = db.Column(db.Text)
    status = db.Column(Enum("IN_PROFRESS", "SUBMITTED", "IN_REVIEW", "REVIEWED"), nullable=False)
    answers = db.Column(db.Text)
    total_score = db.Column(db.Integer)
