from app import app
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_bootstrap import Bootstrap
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from app.auth.form import LoginForm, RegisterForm, bcrypt
from app.models import db, Students, Instructors
#from app.auth.models import db, Students, Instructors
from app.auth.email_verification import send_verification_email, confirm_verification_token

authBp = Blueprint("authBp", __name__, template_folder="templates")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'authBp.login'

@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('student-'):
        print(Students.query.get(int(user_id.split('-')[1])))
        return Students.query.get(int(user_id.split('-')[1]))
    elif user_id.startswith('instructor-'):
        return Instructors.query.get(int(user_id.split('-')[1]))
    return None


@authBp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        user = Students.query.filter_by(email=email).first()
        if not user:
            user = Instructors.query.filter_by(email=email).first()
        
        if user:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. User not found.', 'danger')

    return render_template('login.html', form=form)


@authBp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('authBp.login'))

@authBp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if Students.query.filter_by(email=email).first() or \
           Instructors.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html', form=form)

        role = form.role.data or 'Student'
        
        
        user_data = {
            'role': role,
            'name': form.name.data,
            'email': email,
            'password_hash': bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        }


        if role == 'Student':
            user_data['roll_number'] = form.roll_number.data
            user_data['contact_number'] = form.contact_number.data
        
        try:
            send_verification_email(user_data)
        except Exception as e:
            flash(f"Error sending verification email: {e}", 'danger')
            return render_template('register.html', form=form)
        return redirect(url_for('authBp.verification_sent'))

    return render_template('register.html', form=form)

@authBp.route('/verify_email/<token>')
def verify_email(token):
    data = confirm_verification_token(token)
    if not data:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('authBp.login'))
    
    email = data['email'].lower()
    user = Students.query.filter_by(email=email).first()
    if not user:
        user = Instructors.query.filter_by(email=email).first()
    
    if user:
        flash('Account already verified. Please login.', 'success')
        return redirect(url_for('authBp.login'))

    if data['role'] == 'Student':
        user = Students(
            roll_number=data['roll_number'],
            name=data['name'],
            email=email,
            password_hash=data['password_hash'],
            contact_number=data['contact_number']
        )
    else:
        user = Instructors(
            name=data['name'],
            email=email,
            password_hash=data['password_hash']
        )
    
    db.session.add(user)
    db.session.commit()
    
    flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('authBp.login'))

@authBp.route('/verification_sent')
def verification_sent():
    return render_template('verification_sent.html')