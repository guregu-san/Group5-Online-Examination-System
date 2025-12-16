from flask import Blueprint, render_template


gradingUiBp = Blueprint(
    "gradingUiBp",
    __name__,
    url_prefix="/instructor/grading",
    template_folder="templates"
)


@gradingUiBp.route("", methods=["GET"])
def grading_dashboard():
    # URL: /instructor/grading
    return render_template("manual_grading_dashboard.html")

@gradingUiBp.route("/exams/<int:exam_id>/submissions", methods=["GET"])
def grading_exam_submissions(exam_id):
    # URL: /instructor/grading/exams/123/submissions
    return render_template("exam_submission_list.html", exam_id=exam_id)

@gradingUiBp.route("/submissions/<int:submission_id>", methods=["GET"])
def grading_submission_review(submission_id):
    # URL: /instructor/grading/submissions/456
    return render_template("submission_review.html", submission_id=submission_id)
