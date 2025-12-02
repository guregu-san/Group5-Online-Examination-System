from app import app
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, RadioField
from wtforms.validators import InputRequired, Length, ValidationError, Optional, Email
#from app.auth.models import Students, Instructors
from app.models import Students, Instructors
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

def raise_error():
        raise ValidationError('password or email incorrect')

class LoginForm(FlaskForm):
    email = StringField(validators=[InputRequired()], render_kw={"placeholder": "email"})
    password = PasswordField(validators=[InputRequired()], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')



    def validate_email(self, email):
        user = Students.query.filter_by(email=email.data).first()
        if not user:
            user = Instructors.query.filter_by(email=email.data).first()
        if not user:
            raise_error()

    def validate_password(self, password):
        user = Students.query.filter_by(email=self.email.data).first()
        if not user:
            user = Instructors.query.filter_by(email=self.email.data).first()

        if user and not bcrypt.check_password_hash(user.password_hash, password.data):
            raise_error()






class RegisterForm(FlaskForm):
    email = StringField(validators=[InputRequired(), Length(min=4, max=50)], render_kw={"placeholder": "email"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=50)], render_kw={"placeholder": "Password"})
    role = RadioField('Role', choices=[('Student'), ('Instructor')], default='Student')
    roll_number = StringField(validators=[Optional()], render_kw={"placeholder": "Roll Number"})
    name = StringField(validators=[Optional(), Length(min=2, max=50)], render_kw={"placeholder": "Name"})
    contact_number = StringField(validators=[Optional(), Length(min=10, max=15)], render_kw={"placeholder": "Contact Number"})

    submit = SubmitField('Register')

    def validate_roll_number(self, roll_number):
        if self.role.data == 'Student':
            existing_student_roll_number = Students.query.filter_by(roll_number=roll_number.data).first()
            if existing_student_roll_number:
                raise ValidationError("That roll number is already in use. Please choose a different one.")

    def validate_email(self, email):
        role = self.role.data or 'student'
        if role == 'student':
            existing_user_email = Students.query.filter_by(email=email.data).first()
        else:
            existing_user_email = Instructors.query.filter_by(email=email.data).first()

        if existing_user_email:
            raise ValidationError("That email address is already in use. Please choose a different one.")
