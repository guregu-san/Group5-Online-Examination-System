import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import sqlite3
from app import app


def reset_db():
    conn = sqlite3.connect("oesDB.db")
    cur = conn.cursor()

    cur.executescript("""
    DELETE FROM options;
    DELETE FROM questions;
    DELETE FROM exams;
    DELETE FROM courses;
    DELETE FROM instructors;

    INSERT INTO instructors (name, email, password_hash)
    VALUES ('Teacher One', 'teacher@uni.com', 'pass');

    INSERT INTO courses (course_code, course_name, instructor_email)
    VALUES ('CS101', 'Example Course', 'teacher@uni.com');
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------
# TEST 1 — Create exam (opens_at / closes_at works)
# ---------------------------------------------------
def test_create_exam():
    reset_db()
    client = app.test_client()

    response = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Midterm",
            "opens_at": "2025-12-01 09:00",
            "closes_at": "2025-12-10 20:00",
            "security_settings": "shuffle"
        }),
        content_type="application/json"
    )

    data = response.get_json()
    print("Create exam:", data)

    assert response.status_code == 201
    assert "exam_id" in data


# ---------------------------------------------------
# TEST 2 — List exams (still works)
# ---------------------------------------------------
def test_list_exams():
    reset_db()
    client = app.test_client()

    # create exam
    client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Test Exam",
            "opens_at": "2025-12-01 09:00",
            "closes_at": "2025-12-10 20:00"
        }),
        content_type="application/json"
    )

    response = client.get("/exams/instructor/teacher@uni.com")
    data = response.get_json()
    print("List exams:", data)

    assert response.status_code == 200
    assert isinstance(data, list)
    assert len(data) == 1


# ---------------------------------------------------
# TEST 3 — UI pages render (HTML, not JSON)
# ---------------------------------------------------
def test_exam_create_ui():
    client = app.test_client()
    response = client.get("/exams/create")
    assert response.status_code == 200
    assert b"Create Exam" in response.data


def test_exam_edit_ui():
    reset_db()
    client = app.test_client()

    # create exam
    exam_id = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Edit UI Test",
            "opens_at": "2025-12-01 10:00",
            "closes_at": "2025-12-10 20:00"
        }),
        content_type="application/json"
    ).get_json()["exam_id"]

    response = client.get(f"/exams/{exam_id}/edit")
    assert response.status_code == 200
    assert b"Edit" in response.data or b"Questions" in response.data
