import sqlite3
import json
from flask import Blueprint, request, jsonify, render_template
#from app import app

# ---- Blueprint ---- 
exam_createBp = Blueprint('exam_create', __name__, url_prefix="/create", template_folder='templates')


@exam_createBp.route('/', methods=['GET', 'POST'])
def create():
    # Show the exam creation page. If you later add POST handling, implement it here.
    return render_template('exam_create.html')