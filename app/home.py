from flask import Flask, render_template, redirect, url_for
from app import app
from flask_login import login_required, current_user


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/home', methods=['GET'])
def homePage():
    return render_template('home.html')
