'''Third-party packages'''
from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
bcrypt = Bcrypt()

app = Flask(__name__)

app.config['SECRET_KEY'] = 'dupa123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../oesDB.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

bs = Bootstrap(app)
db.init_app(app)
bcrypt.init_app(app)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500

'''Local packages'''
from app import home
from app.auth.auth import authBp
from app.exam.exam import examBp
from .take_exam.take_exam import takeExamBp
from .view_exams import exam_viewBp
from .exam_create import exam_createBp

app.register_blueprint(authBp)
app.register_blueprint(examBp)
app.register_blueprint(takeExamBp)
app.register_blueprint(exam_viewBp)
app.register_blueprint(exam_createBp)
