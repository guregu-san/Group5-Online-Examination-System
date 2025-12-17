from app import app
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, RadioField
from wtforms.validators import InputRequired, Length, ValidationError, Optional, Email, Regexp
#from app.auth.models import Students, Instructors
from app.models import Students, Instructors
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(app)

class LoginForm(FlaskForm):
    email = StringField(render_kw={"placeholder": "email"}, filters=[lambda x: x.strip() if x else None])
    password = PasswordField(render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')

    def validate_password(self, password):
        if not password.data or not self.email.data:
            raise ValidationError('insert email or password')
        email_data = self.email.data.lower()
            
        user = Students.query.filter_by(email=email_data).first()
        if not user:
            user = Instructors.query.filter_by(email=email_data).first()
        
        if user and not bcrypt.check_password_hash(user.password_hash, password.data):
            raise ValidationError('password or email incorrect')


class RegisterForm(FlaskForm):
    email = StringField(
        render_kw={"placeholder": "email"},
        filters=[lambda x: x.strip() if x else None],
        validators=[
            InputRequired(),
            Length(min=4, max=50),
            Regexp(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', message="Invalid email address.")
        ]
    )
    password = PasswordField(render_kw={"placeholder": "Password"})
    role = RadioField('Role', choices=[('Student', 'Student'), ('Instructor', 'Instructor')], default='Student')
    roll_number = StringField(render_kw={"placeholder": "Roll Number"}, filters=[lambda x: x.strip() if x else None])
    name = StringField(render_kw={"placeholder": "Name"}, filters=[lambda x: x.strip() if x else None])
    contact_number = StringField(
        render_kw={"placeholder": "Contact Number"},
        filters=[lambda x: x.strip() if x else None],
        validators=[
            InputRequired(),
            Regexp(r'^\d{10,15}$', message="Contact number must be 10 to 15 digits.")
        ]
    )
    
    submit = SubmitField('Register')

    def validate_email(self, email):
        email_data = email.data.lower()
        role = self.role.data or 'Student'
        if role == 'Student':
            existing_user_email = Students.query.filter_by(email=email_data).first()
        else:
            existing_user_email = Instructors.query.filter_by(email=email_data).first()
        
        if existing_user_email:
            raise ValidationError("Email already exists.")

    def validate_password(self, password):
        if not password.data:
            raise ValidationError("Password is required.")
        if len(password.data) < 6 or len(password.data) > 20:
            raise ValidationError("Password must be between 6 and 20 characters.")

    def validate_roll_number(self, roll_number):
        if self.role.data == 'Student':
            if not roll_number.data:
                raise ValidationError("Roll Number is required for Students.")
            existing_student_roll_number = Students.query.filter_by(roll_number=roll_number.data).first()
            if existing_student_roll_number:
                raise ValidationError("That roll number is already in use. Please choose a different one.")

    def validate_name(self, name):
        if not name.data:
            raise ValidationError("Name is required.")
        if len(name.data) < 2 or len(name.data) > 20:
            raise ValidationError("Name must be between 2 and 20 characters.")

    def validate_contact_number(self, contact_number):
        if self.role.data == 'Student':
            if not contact_number.data:
                raise ValidationError("Contact Number is required for Students.")
            
            existing_student_contact = Students.query.filter_by(contact_number=contact_number.data).first()
            if existing_student_contact:
                raise ValidationError("That contact number is already in use. Please choose a different one.")
        else:
            if contact_number.data and (len(contact_number.data) < 10 or len(contact_number.data) > 15):
                raise ValidationError("Contact Number must be between 10 and 15 characters.")
            
            