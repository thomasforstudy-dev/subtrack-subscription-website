"""AI tools: one page that links to the spending forecast, Read aloud and
the food roulette (each lives in its own file), plus three small games.

The games (coin flip, blackjack, case spin) run entirely in the browser:
nothing is saved on the server and no money is involved, so each route
only renders its page."""

from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint("tools", __name__, url_prefix="/tools")


@bp.get("/")
@login_required
def index():
    return render_template("tools/index.html")


@bp.get("/coin-flip")
@login_required
def coin_flip():
    return render_template("tools/coin_flip.html")


@bp.get("/blackjack")
@login_required
def blackjack():
    return render_template("tools/blackjack.html")


@bp.get("/case-spin")
@login_required
def case_spin():
    return render_template("tools/case_spin.html")
