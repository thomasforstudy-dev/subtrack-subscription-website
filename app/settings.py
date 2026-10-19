"""Settings page: time zone and reminder choices."""

from zoneinfo import available_timezones

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.reminders import CHANNELS

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
