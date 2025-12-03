from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional  # ⬅️ NO Email here

class ExamCreateForm(FlaskForm):
    course_code = StringField("Course Code", validators=[DataRequired()])
    instructor_email = StringField("Instructor Name or Email", validators=[DataRequired()])
    title = StringField("Exam Title", validators=[DataRequired()])
    time_limit = IntegerField(
        "Time Limit (minutes)",
        validators=[Optional(), NumberRange(min=1, max=600, message="Time limit must be between 1 and 600 minutes")],
    )
    security_settings = StringField("Security Settings", validators=[Optional()])
    submit = SubmitField("Create Exam")
