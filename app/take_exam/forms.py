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
from wtforms.validators import InputRequired, Length, Optional
from wtforms.widgets import ListWidget, CheckboxInput


class ExamSearchForm(FlaskForm):
    examID = StringField(validators=[InputRequired(), Length(min=1, max=16)], render_kw={"placeholder": "Enter Exam ID"})

    submit = SubmitField('Search')


class ExamInitializationForm(FlaskForm):
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Enter Exam Password"})

    submit = SubmitField('Accept')


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

    answer_single = RadioField(choices=[], coerce=int, validators=[Optional()]) #Might have to change coerce
    answer_multi = MultiCheckboxField(choices=[], coerce=int, validators=[Optional()])

class SubmissionForm(FlaskForm):
    """Top-level submission form with a dynamic list of questions."""
    questions = FieldList(FormField(QuestionAnswerForm), min_entries=1)

    submit = SubmitField('Submit')