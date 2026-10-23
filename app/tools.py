"""AI tools: one page that links to the spending forecast, Read aloud and
the food roulette (each lives in its own file)."""

from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("tools", __name__, url_prefix="/tools")


@bp.get("/")
@login_required
def index():
    return render_template("tools/index.html")
