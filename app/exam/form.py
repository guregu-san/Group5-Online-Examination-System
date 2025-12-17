from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Email, Optional


class ExamCreateForm(FlaskForm):
    # FIXED: No more instructor name allowed — email only
    course_code = StringField(
        "Course Code",
        validators=[DataRequired(message="Course code is required.")]
    )

    instructor_email = StringField(
        "Instructor Email",
        validators=[
            DataRequired(message="Instructor email is required."),
            Email(message="Please enter a valid email address.")
        ]
    )

    title = StringField(
        "Exam Title",
        validators=[DataRequired(message="Exam title is required.")]
    )

    # NEW: Start & end times (datetime-local)
    opens_at = DateTimeLocalField(
        "Opens At",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Please select an opening date and time.")]
    )

    closes_at = DateTimeLocalField(
        "Closes At",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Please select a closing date and time.")]
    )

    # Security settings stored as JSON or blank
    security_settings = StringField(
        "Security Settings (JSON)",
        validators=[Optional()]
    )

    submit = SubmitField("Create Exam")
