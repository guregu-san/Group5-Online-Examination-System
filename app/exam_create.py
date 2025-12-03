from flask import Blueprint, redirect, url_for

# Old blueprint, now just a thin wrapper
exam_createBp = Blueprint(
    "exam_create",
    __name__,
    url_prefix="/create"
)

@exam_createBp.route("/", methods=["GET", "POST"])
def create():
    # Always send user to the real create page in examBp
    return redirect(url_for("examBp.create_exam_ui"))
