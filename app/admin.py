from functools import wraps

import click
from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from app import db
from app.models import Subscription, User

# cli_group=None: the command is "flask make-admin", not "flask admin make-admin".
bp = Blueprint("admin", __name__, url_prefix="/admin", cli_group=None)


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


@bp.cli.command("make-admin")
@click.argument("who")
@click.option("--remove", is_flag=True, help="Take admin rights away instead.")
def make_admin(who: str, remove: bool):
    """Give (or take away) admin rights. WHO is an email or a username.

    Only someone who can run commands on the server PC can do this, so no
    visitor can make themselves admin through the website.
    """
    from app.auth import find_user

    user = find_user(who)
    if user is None:
        raise click.ClickException(f"No account found for {who!r}.")
    if remove:
        if user.is_admin and User.query.filter_by(is_admin=True).count() == 1:
            raise click.ClickException("That is the last admin. Make someone else admin first.")
        user.is_admin = False
    else:
        user.is_admin = True
    db.session.commit()
    click.echo(f"{user.username} ({user.email}) is {'no longer' if remove else 'now'} an admin.")
