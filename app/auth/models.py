'''
from app import db
from flask_login import UserMixin


class Students(db.Model, UserMixin):
    roll_number = db.Column(db.Integer, primary_key=True, nullable=True)
    name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    contact_number = db.Column(db.Integer, nullable=True)
    role = "Student"

    def get_id(self):
        return f"student-{self.roll_number}"


class Instructors(db.Model, UserMixin):
    instructor_id = db.Column(db.Integer, primary_key=True, nullable=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(80), nullable=False)
    role = "Instructor"

    def get_id(self):
        return f"instructor-{self.instructor_id}"
'''
