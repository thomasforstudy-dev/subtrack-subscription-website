"""User guide: the steps a new user takes, each with a picture of the button
to look for and a "Show me" button that starts the guided tour (static/tour.js)
at that step. Anyone can read it; the tour itself needs an account."""

from flask import Blueprint, render_template

bp = Blueprint("guide", __name__)


@bp.get("/guide")
def show():
    return render_template("guide.html")
