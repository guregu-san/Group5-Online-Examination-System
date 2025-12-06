from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SubmitField,
    PasswordField,
    Form,
    FormField,
    FieldList,
    HiddenField,
    RadioField,
    SelectMultipleField,
)
from wtforms.validators import InputRequired, Length, Optional, ValidationError
from wtforms.widgets import ListWidget, CheckboxInput

from app.models import Exams


class ExamSearchForm(FlaskForm):
    examID = StringField(validators=[InputRequired(), Length(min=1, max=16)], render_kw={"placeholder": "Enter exam ID"})
    submit = SubmitField('Search')

    def validate_examID(self, examID):
        exam = Exams.query.get(examID.data)
        if not exam:
            raise ValidationError('Exam not found')


class ExamInitializationForm(FlaskForm):
    exam_id = HiddenField()
    password = PasswordField(validators=[Length(min=0, max=20)], render_kw={"placeholder": "Enter exam password"})
    accept = SubmitField('Accept')
    cancel = SubmitField('Cancel')
    continue_submission = SubmitField('Continue')

    def validate_password(self, password):
        if self.cancel.data:
            return

        exam = Exams.query.get(self.exam_id.data)
        if not exam:
            raise ValidationError('Exam not found')

        # For debugging
        print("Input: ", password.data, '\nCorrect: ', exam.security_settings["password"])
        if exam.security_settings["password"] != "" and password.data != exam.security_settings["password"]:
            raise ValidationError('Incorrect password')


class MultiCheckboxField(SelectMultipleField):
    """Multiple-select, displayed as a list of checkboxes."""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class QuestionAnswerForm(Form):
    """A subform describing one question's answer(s).

    - `question_id`: HiddenField to carry the question identifier.
    - `single_or_multi`: HiddenField set to 'single' or 'multi'.
    - `answer_single`: RadioField for single-choice questions.
    - `answer_multi`: MultiCheckboxField for multi-choice questions.
    """
    question_id = HiddenField()
    single_or_multi = HiddenField()
    answer_single = RadioField(choices=[], coerce=int, validators=[Optional()])
    answer_multi = MultiCheckboxField(choices=[], coerce=int, validators=[Optional()])

class SubmissionForm(FlaskForm):
    """Top-level submission form with a dynamic list of questions."""
    questions = FieldList(FormField(QuestionAnswerForm), min_entries=1)
    submit = SubmitField('Submit')
    save = SubmitField('Save and Exit')
