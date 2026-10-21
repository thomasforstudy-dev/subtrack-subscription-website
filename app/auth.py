"""Accounts: sign up, log in, log out, confirm email, forgot / reset password.

Form fields and routes are listed in docs/CONTRACT.md.
"""

import logging
import os
import re
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app import api_tokens, db, email_codes, tokens
from app.mailer import Email, MailError, MailNotReady, external_url, mail_ready, send_email
from app.models import User, utcnow
from app.schedule import user_zone
from app.security import RateLimiter, client_ip, safe_next_url
from app.validation import (
    email_error,
    normalize_email,
    normalize_username,
    password_error,
    username_error,
)

bp = Blueprint("auth", __name__)
log = logging.getLogger(__name__)

VERIFY_MINUTES = 24 * 60
RESET_MINUTES = 30
LOCKOUT_MINUTES = 15

# Wrong passwords: 5 per account from one address, 30 from one address in total.
failed_logins = RateLimiter(5, LOCKOUT_MINUTES * 60)
failed_logins_per_ip = RateLimiter(30, LOCKOUT_MINUTES * 60)
# "Forgot password" and "resend the confirm email": 5 per hour per address.
email_requests = RateLimiter(5, 60 * 60)
# Wrong 6-digit codes: 5 per account, then the code is cancelled.
wrong_codes = RateLimiter(5, LOCKOUT_MINUTES * 60)

# Checked when nobody has that email, so a wrong email takes as long as a
# wrong password and the timing doesn't reveal which accounts exist.
_DUMMY_HASH = generate_password_hash(secrets.token_urlsafe(16))

RESET_SENT = (
    "If that email has an account, we've sent it a link to reset the password. "
    f"The link works for {RESET_MINUTES} minutes."
)


def show(template: str, status: int = 200):
    """Render a log in / sign up page with the Google/GitHub buttons that are set up."""
    from app.oauth import enabled_providers

    return render_template(template, providers=enabled_providers()), status


def unique_username(email: str) -> str:
    """Pick a free username from an email, e.g. "toan.bui@x.com" -> "toanbui"."""
    base = re.sub(r"[^a-z0-9_]", "", normalize_username(email.split("@")[0]))
    base = (base or "user")[:24].ljust(3, "_")
    name = base
    while User.query.filter_by(username=name).first():
        name = f"{base}{secrets.randbelow(9000) + 1000}"
    return name


def create_user(email: str, password: str | None = None, username: str | None = None,
                verified: bool = False) -> User:
    """Make an account. Nobody becomes admin here: use `flask make-admin`."""
    user = User(
        email=email,
        username=username or unique_username(email),
        timezone=user_zone(os.getenv("DEFAULT_TIMEZONE")).key,  # they can change it in Settings
    )
    # Google/GitHub users have no password. A long random one means nobody
    # can log in to their account with a password at all.
    user.set_password(password or secrets.token_urlsafe(32))
    if verified:
        user.email_verified_at = utcnow()
    db.session.add(user)
    db.session.commit()
    return user


def find_user(identifier: str) -> User | None:
    """Look someone up by email (has an @) or by username."""
    if "@" in identifier:
        return User.query.filter_by(email=normalize_email(identifier)).first()
    return User.query.filter_by(username=normalize_username(identifier)).first()


def finish_login(user: User, next_url: str | None = None):
    user.last_login_at = utcnow()
    db.session.commit()
    # Start a brand-new session, so nothing from before logging in carries
    # over (except messages waiting to be shown, like "Welcome!").
    messages = session.get("_flashes", [])
    session.clear()
    if messages:
        session["_flashes"] = messages
    login_user(user)
    return redirect(safe_next_url(next_url) or url_for("subscriptions.list_subscriptions"))


def send_verification(user: User) -> bool:
    """Email a "confirm your email" link and a 6-digit code (either one works).
    Returns False if it couldn't be sent."""
    raw = tokens.issue(user, "verify_email", VERIFY_MINUTES)
    link = external_url("auth.verify_email", token=raw)
    code = email_codes.issue(user)  # only the newest code works
    wrong_codes.reset(f"user-{user.id}")  # a fresh code gets fresh tries
    return _send(Email(
        to=user.email,
        subject=f"{code} is your AllOutFree code",
        text=(
            f"Hi {user.username},\n\nYour AllOutFree code is: {code}\n\n"
            f"Type it in the yellow box on AllOutFree (it works for {email_codes.MINUTES} minutes), "
            f"or click this link instead (it works for 24 hours):\n\n{link}\n\n"
            "Confirming your email lets AllOutFree send your renewal reminders. "
            "If you didn't sign up, you can ignore this email. Never share the code with anyone."
        ),
        idempotency_key=f"verify-{user.id}-{raw[:16]}",
    ))


def send_reset(user: User) -> bool:
    raw = tokens.issue(user, "reset_password", RESET_MINUTES)
    link = external_url("auth.reset_password", token=raw)
    return _send(Email(
        to=user.email,
        subject="Reset your AllOutFree password",
        text=(
            f"Hi {user.username},\n\nSomeone (hopefully you) asked to reset your "
            f"AllOutFree password. Choose a new one here:\n\n{link}\n\n"
            f"The link works for {RESET_MINUTES} minutes and only once. "
            "If it wasn't you, ignore this email: your password stays the same."
        ),
        idempotency_key=f"reset-{user.id}-{raw[:16]}",
    ))


def _send(email: Email) -> bool:
    try:
        send_email(email)
        return True
    except (MailNotReady, MailError) as exc:
        log.warning("Email not sent: %s", exc)  # never logs the link itself
        return False


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))
    if request.method == "GET":
        return show("auth/register.html")

    username = normalize_username(request.form.get("username", ""))
    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm") or ""

    if not username or not email or not password:
        error = "Please fill in username, email and password."
    else:
        error = username_error(username) or email_error(email) or password_error(password)
    if not error and password != confirm:
        error = "The two passwords don't match. Please type them again."
    if not error and User.query.filter_by(username=username).first():
        error = "That username is taken. Please try another one."
    if not error and User.query.filter_by(email=email).first():
        error = "That email is already registered. Try logging in instead."
    if error:
        flash(error)
        return show("auth/register.html")

    try:
        user = create_user(email, password, username)
    except IntegrityError:  # someone took it in the same second
        db.session.rollback()
        flash("That username or email was just taken. Please try another one.")
        return show("auth/register.html")

    if send_verification(user):
        flash("Welcome! We've emailed you a 6-digit code: type it in the yellow box (or click the link in the email).")
    else:
        flash("Welcome! We couldn't send the confirmation email right now. You can resend it later.")
    return finish_login(user)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))
    if request.method == "GET":
        return show("auth/login.html")

    # "email" is the old field name; it still works.
    identifier = (request.form.get("identifier") or request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    ip = client_ip()
    account_key = f"{ip}|{identifier.lower()}"

    if failed_logins_per_ip.is_blocked(ip) or failed_logins.is_blocked(account_key):
        flash(f"Too many tries. Please wait {LOCKOUT_MINUTES} minutes, or reset your password.")
        return show("auth/login.html", 429)

    user = find_user(identifier) if identifier else None
    if user is None:
        check_password_hash(_DUMMY_HASH, password)  # same work as a real check
        ok = False
    else:
        ok = user.check_password(password)
    if not ok:
        failed_logins.hit(account_key)
        failed_logins_per_ip.hit(ip)
        flash("Wrong email/username or password.")
        return show("auth/login.html")

    failed_logins.reset(account_key)
    return finish_login(user, request.args.get("next"))


@bp.post("/logout")
@login_required
def logout():
    # POST only (with the CSRF token), so another website can't log people out.
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/verify-email/<token>", methods=["GET", "POST"])
def verify_email(token: str):
    # Opening the link only shows a button. Some email apps open every link
    # to scan it, and that must not use the link up.
    if request.method == "GET":
        valid = tokens.find_valid(token, "verify_email") is not None
        return render_template("auth/verify.html", valid=valid)

    user = tokens.use(token, "verify_email")
    if user is None:
        flash("That link has expired or was already used. Log in and ask for a new one.")
        return redirect(url_for("auth.login"))
    user.email_verified_at = user.email_verified_at or utcnow()
    db.session.commit()
    flash("Thanks! Your email is confirmed.")
    if current_user.is_authenticated:
        return redirect(url_for("subscriptions.list_subscriptions"))
    return redirect(url_for("auth.login"))


@bp.post("/verify-email/code")
@login_required
def verify_code():
    """The 6-digit code from the email, typed into the yellow banner."""
    back = safe_next_url(request.form.get("next")) or url_for("subscriptions.list_subscriptions")
    if current_user.email_verified:
        flash("Your email is already confirmed.")
        return redirect(back)
    key = f"user-{current_user.id}"
    if wrong_codes.is_blocked(key):
        flash("Too many wrong codes. Please send yourself a new one.")
        return redirect(back)
    code = "".join((request.form.get("code") or "").split())  # "123 456" is fine too
    if not (re.fullmatch(r"[0-9]{6}", code) and email_codes.use(current_user, code)):
        wrong_codes.hit(key)
        if wrong_codes.is_blocked(key):
            # Someone guessing gets no more tries at this code.
            email_codes.cancel_all(current_user)
            flash("That was the 5th wrong code, so we cancelled it. Please send yourself a new one.")
        else:
            flash("That code isn't right or has expired. Check the newest email from AllOutFree.")
        return redirect(back)
    current_user.email_verified_at = current_user.email_verified_at or utcnow()
    db.session.commit()
    wrong_codes.reset(key)
    flash("Thanks! Your email is confirmed.")
    return redirect(back)


@bp.post("/verify-email/resend")
@login_required
def resend_verification():
    back = url_for("subscriptions.list_subscriptions")
    if current_user.email_verified:
        flash("Your email is already confirmed.")
    elif not email_requests.hit(f"user-{current_user.id}"):
        flash("We've sent a few emails already. Please check your spam folder, or try again in an hour.")
    elif send_verification(current_user):
        flash(f"Sent! Check {current_user.email} for the new code (older codes stop working).")
    else:
        flash("We couldn't send the email right now. Please try again later.")
    return redirect(back)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("auth/forgot.html")

    # Every answer below is the same for every email, so this page can't be
    # used to find out who has an account.
    if not mail_ready():
        flash("Password reset emails aren't switched on yet. Please contact us for help.")
        return render_template("auth/forgot.html")
    if not email_requests.hit(f"ip-{client_ip()}"):
        flash("Too many requests. Please try again in an hour.")
        return render_template("auth/forgot.html"), 429

    email = normalize_email(request.form.get("email", ""))
    user = User.query.filter_by(email=email).first() if email else None
    if user is not None:
        send_reset(user)
    flash(RESET_SENT)
    return redirect(url_for("auth.login"))


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if tokens.find_valid(token, "reset_password") is None:
        flash("That reset link has expired or was already used. Please ask for a new one.")
        return redirect(url_for("auth.forgot_password"))
    if request.method == "GET":
        return render_template("auth/reset.html")

    password = request.form.get("password") or ""
    error = password_error(password)
    if not error and password != (request.form.get("confirm") or ""):
        error = "The two passwords don't match. Please type them again."
    if error:
        flash(error)
        return render_template("auth/reset.html")

    user = tokens.use(token, "reset_password")
    if user is None:
        flash("That reset link has expired or was already used. Please ask for a new one.")
        return redirect(url_for("auth.forgot_password"))
    user.set_password(password)  # also logs out every other browser (see User.session_key)
    api_tokens.revoke_all(user)  # and disconnects every extension: recovery means a clean slate
    # The link reached their inbox, so the email address is theirs.
    user.email_verified_at = user.email_verified_at or utcnow()
    db.session.commit()
    tokens.cancel_all(user, "reset_password")
    flash("Password changed. Please log in with your new password.")
    return redirect(url_for("auth.login"))
