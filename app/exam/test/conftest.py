import sys
import os
import pytest

# Add project root to Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
sys.path.insert(0, ROOT_DIR)

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def exam_id(client):
    """
    Create an exam and return a dummy exam_id.
    We simulate the ID because the real DB is not seeded in tests.
    """
    client.post(
        "/exams/create",
        data={
            "course_code": "CS101",
            "instructor_email": "instructor@test.com",
            "title": "Pytest Exam",
            "opens_at": "2025-01-01T10:00",
            "closes_at": "2025-01-01T12:00",
        },
        follow_redirects=True,
    )
    return 1


@pytest.fixture
def question_id(exam_id):
    """
    Dummy question ID linked to an exam.
    """
    return 1
