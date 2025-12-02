from app import app
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from app.auth.form import LoginForm, RegisterForm, bcrypt
from app.models import db, Students, Instructors
#from app.auth.models import db, Students, Instructors

authBp = Blueprint("authBp", __name__, template_folder="templates")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'authBp.login'

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('student-'):
        return Students.query.get(int(user_id.split('-')[1]))
    elif user_id.startswith('instructor-'):
        return Instructors.query.get(int(user_id.split('-')[1]))
    return None


@authBp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Students.query.filter_by(email=form.email.data).first()
        if not user:
            user = Instructors.query.filter_by(email=form.email.data).first()
        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('login.html', form=form)


@authBp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('authBp.login'))

@authBp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        role = form.role.data or 'Student'
        if role == 'Student':
            student = Students(
                roll_number = form.roll_number.data,
                name = form.name.data,
                email = form.email.data,
                password_hash = bcrypt.generate_password_hash(form.password.data),
                contact_number = form.contact_number.data,
            )
            db.session.add(student)
        else:
            instructor = Instructors(
                name = form.name.data,
                email = form.email.data,
                password_hash = bcrypt.generate_password_hash(form.password.data),
            )
            db.session.add(instructor)

        db.session.commit()
        return redirect(url_for('authBp.login'))

    return render_template('register.html', form=form)
