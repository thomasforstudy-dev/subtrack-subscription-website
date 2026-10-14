from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    # Logged-in users go straight to their list; visitors see the story page.
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))
    return render_template("landing.html")
