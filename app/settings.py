"""Settings page: time zone and reminder choices."""

from zoneinfo import available_timezones

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.mailer import Email, MailError, MailNotReady, external_url, send_email
from app.reminders import CHANNELS
from app.security import RateLimiter

bp = Blueprint("settings", __name__)

# Every IANA time zone ("Asia/Ho_Chi_Minh", "Europe/London", ...), from tzdata.
ZONES = sorted(available_timezones())


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def show():
    if request.method == "POST":
        zone = (request.form.get("timezone") or "").strip()
        if zone not in ZONES:
            flash("Please pick a time zone from the list.")
            return render_template("settings.html", zones=ZONES, channels=CHANNELS)
        try:
            hour = int(request.form.get("reminder_hour", ""))
        except ValueError:
            hour = -1
        if not 0 <= hour <= 23:
            flash("Pick an hour from 0 to 23.")
            return render_template("settings.html", zones=ZONES, channels=CHANNELS)

        current_user.timezone = zone
        current_user.reminder_hour = hour
        current_user.reminders_enabled = request.form.get("reminders_enabled") == "on"
        chosen = [c for c in request.form.getlist("channels") if c in CHANNELS]
        current_user.reminder_channels = ",".join(chosen)
        db.session.commit()
        flash("Settings saved.")
        return redirect(url_for("settings.show"))
    return render_template("settings.html", zones=ZONES, channels=CHANNELS)


test_emails = RateLimiter(3, 3600)  # per user per hour: enough to check, not to spam


@bp.post("/settings/test-email")
@login_required
def test_email():
    """Send a sample reminder to the user's own address, so they can see what
    one looks like and check it doesn't land in spam."""
    if not current_user.email_verified:
        flash("Confirm your email first, then try the test email.")
    elif not test_emails.hit(f"user:{current_user.id}"):
        flash("You've sent a few test emails already. Please try again in an hour.")
    else:
        hour = f"{current_user.reminder_hour:02d}:00"
        try:
            send_email(Email(
                to=current_user.email,
                subject="Test: your AllOutFree reminders work",
                text="\n".join([
                    f"Hi {current_user.username or current_user.email},",
                    "",
                    "This is a test. Real reminders look like this one and arrive at "
                    f"{hour} ({current_user.timezone}), before each renewal.",
                    "",
                    f"Change your reminder settings: {external_url('settings.show')}",
                ]),
            ))
            flash("Test email sent. Check your inbox (and the spam folder).")
        except (MailNotReady, MailError):
            flash("We couldn't send the email right now. Please try again later.")
    return redirect(url_for("settings.show"))


@bp.route("/settings.json")
@login_required
def as_json():
    """The saved settings, for pages that show them in a panel. They live on
    the server (reminders use them), not in the browser. Change them with
    POST /settings."""
    return jsonify(
        timezone=current_user.timezone,
        reminders_enabled=current_user.reminders_enabled,
        reminder_hour=current_user.reminder_hour,
        channels=current_user.channel_list,
        available_channels=list(CHANNELS),
    )
