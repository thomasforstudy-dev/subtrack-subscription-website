from functools import wraps

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from app.models import Subscription, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@bp.route("/users")
@login_required
@admin_required
def users():
    accounts = User.query.order_by(User.created_at.desc()).all()
    counts = {
        user.id: Subscription.query.filter_by(user_id=user.id).count()
        for user in accounts
    }
    return render_template("admin/users.html", accounts=accounts, counts=counts)
