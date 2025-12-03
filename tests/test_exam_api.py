import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import sqlite3
from app import app


# Helper to reset the DB for consistent test results
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


def test_create_exam():
    reset_db()
    client = app.test_client()

    response = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Midterm",
            "time_limit": 60,
            "security_settings": "shuffle=true"
        }),
        content_type="application/json"
    )

    data = json.loads(response.data)
    print("Create exam:", data)

    assert response.status_code == 201
    assert "exam_id" in data


def test_add_question():
    reset_db()
    client = app.test_client()

    # first create exam
    exam_resp = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Quiz",
            "time_limit": 45
        }),
        content_type="application/json"
    )
    exam_id = exam_resp.get_json()["exam_id"]

    # add question
    response = client.post(
        f"/exams/{exam_id}/questions",
        data=json.dumps({
            "question_text": "What is 2+2?",
            "is_multiple_correct": False,
            "points": 5,
            "options": [
                {"option_text": "3", "is_correct": False},
                {"option_text": "4", "is_correct": True}
            ]
        }),
        content_type="application/json"
    )

    data = response.get_json()
    print("Add question:", data)

    assert response.status_code == 201
    assert "question_id" in data


def test_edit_question():
    reset_db()
    client = app.test_client()

    # create exam
    exam_id = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Quiz"
        }),
        content_type="application/json"
    ).get_json()["exam_id"]

    # add question
    q_id = client.post(
        f"/exams/{exam_id}/questions",
        data=json.dumps({
            "question_text": "Old Question?",
            "is_multiple_correct": False,
            "options": [
                {"option_text": "X", "is_correct": True}
            ]
        }),
        content_type="application/json"
    ).get_json()["question_id"]

    # edit it
    response = client.patch(
        f"/exams/questions/{q_id}",
        data=json.dumps({
            "question_text": "Updated Question?",
            "points": 10,
            "options": [
                {"option_text": "Correct", "is_correct": True}
            ]
        }),
        content_type="application/json"
    )

    print("Edit question:", response.get_json())
    assert response.status_code == 200


def test_delete_question():
    reset_db()
    client = app.test_client()

    # create exam
    exam_id = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Quiz"
        }),
        content_type="application/json"
    ).get_json()["exam_id"]

    # add question
    q_id = client.post(
        f"/exams/{exam_id}/questions",
        data=json.dumps({
            "question_text": "Delete me?",
            "is_multiple_correct": False,
            "options": [
                {"option_text": "Yes", "is_correct": True}
            ]
        }),
        content_type="application/json"
    ).get_json()["question_id"]

    # delete it
    response = client.delete(f"/exams/questions/{q_id}")
    print("Delete question:", response.get_json())

    assert response.status_code == 200


def test_reorder_questions():
    reset_db()
    client = app.test_client()

    # create exam
    exam_id = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com",
            "title": "Quiz"
        }),
        content_type="application/json"
    ).get_json()["exam_id"]

    # add 2 questions
    q1 = client.post(
        f"/exams/{exam_id}/questions",
        data=json.dumps({
            "question_text": "Q1?",
            "is_multiple_correct": False,
            "options": [{"option_text": "A", "is_correct": True}]
        }),
        content_type="application/json"
    ).get_json()["question_id"]

    q2 = client.post(
        f"/exams/{exam_id}/questions",
        data=json.dumps({
            "question_text": "Q2?",
            "is_multiple_correct": False,
            "options": [{"option_text": "A", "is_correct": True}]
        }),
        content_type="application/json"
    ).get_json()["question_id"]

    # reorder
    response = client.post(
        f"/exams/{exam_id}/reorder",
        data=json.dumps({
            "order": [
                {"question_id": q2, "order_index": 1},
                {"question_id": q1, "order_index": 2}
            ]
        }),
        content_type="application/json"
    )

    print("Reorder:", response.get_json())
    assert response.status_code == 200


def test_update_exam_options():
    reset_db()
    client = app.test_client()

    exam_id = client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com"
        }),
        content_type="application/json"
    ).get_json()["exam_id"]

    response = client.patch(
        f"/exams/{exam_id}/options",
        data=json.dumps({
            "title": "Updated Title",
            "time_limit": 120,
            "security_settings": "shuffle_questions"
        }),
        content_type="application/json"
    )

    print("Update exam options:", response.get_json())
    assert response.status_code == 200


def test_list_exams():
    reset_db()
    client = app.test_client()

    client.post(
        "/exams",
        data=json.dumps({
            "course_code": "CS101",
            "instructor_email": "teacher@uni.com"
        }),
        content_type="application/json"
    )

    response = client.get("/exams/instructor/teacher@uni.com")
    print("List exams:", response.get_json())

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)
