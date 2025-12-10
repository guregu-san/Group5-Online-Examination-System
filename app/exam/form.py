from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Optional


class ExamCreateForm(FlaskForm):
    course_code = StringField("Course Code", validators=[DataRequired()])
    instructor_email = StringField("Instructor Name or Email", validators=[DataRequired()])
    title = StringField("Exam Title", validators=[DataRequired()])

    # NEW: start and end date/time
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

    security_settings = StringField("Security Settings", validators=[Optional()])
    submit = SubmitField("Create Exam")
