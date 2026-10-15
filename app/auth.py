import secrets
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models import User

bp = Blueprint("auth", __name__)

MIN_PASSWORD = 8


def show(template: str):
    """Render a log in / sign up page with the Google/GitHub buttons that are set up."""
    from app.oauth import enabled_providers

    return render_template(template, providers=enabled_providers())


def create_user(email: str, password: str | None = None) -> User:
    user = User(email=email)
    # Google/GitHub users have no password. A long random one means nobody
    # can log in to their account with a password at all.
    user.set_password(password or secrets.token_urlsafe(32))
    if User.query.count() == 0:
        user.is_admin = True  # the very first account becomes the admin
    db.session.add(user)
    db.session.commit()
    return user


def finish_login(user: User):
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    login_user(user)
    return redirect(url_for("subscriptions.list_subscriptions"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not email or not password:
            flash("Email and password are required.")
            return show("auth/register.html")
        if len(password) < MIN_PASSWORD:
            flash(f"Your password needs at least {MIN_PASSWORD} characters.")
            return show("auth/register.html")
        if password != confirm:
            flash("The two passwords don't match. Please type them again.")
            return show("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("That email is already registered.")
            return show("auth/register.html")

        return finish_login(create_user(email, password))

    return show("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Invalid email or password.")
            return show("auth/login.html")
        return finish_login(user)

    return show("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
