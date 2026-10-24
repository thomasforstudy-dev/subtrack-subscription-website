"""Manual calendar links and private ICS downloads; no API keys or live sync."""

import re
from calendar import Calendar as MonthCalendar
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from flask import Blueprint, Response, render_template
from flask_login import current_user, login_required

from app.models import Subscription
from app.schedule import local_now, user_zone

bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@bp.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def own_active():
    return Subscription.query.filter_by(user_id=current_user.id, status="active")


def own_item(item_id):
    return own_active().filter_by(id=item_id).first_or_404()


def google_link(item, zone):
    """Only title/date/timezone leave the site when the user opens this URL."""
    start = item.next_renewal_at
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE", "text": f"Renewal: {item.name}",
        "dates": f"{start:%Y%m%d}/{start + timedelta(days=1):%Y%m%d}", "ctz": zone,
    })


def escape_text(value):
    value = str(value).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold_line(line):
    """RFC 5545: at most 75 octets, never split a UTF-8 character."""
    parts, current, size = [], "", 0
    for character in line:
        length = len(character.encode("utf-8"))
        if size + length > 75:
            parts.append(current)
            current, size = " ", 1
        current += character
        size += length
    parts.append(current)
    return "\r\n".join(parts)


def calendar_bytes(items, user_id, zone):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//AllOutFree//Renewals//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:AllOutFree renewals",
             "X-WR-TIMEZONE:" + escape_text(zone)]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for item in items:
        uid = uuid5(NAMESPACE_URL, f"subtrack:renewal:{user_id}:{item.id}")
        start = item.next_renewal_at
        lines.extend([
            "BEGIN:VEVENT", f"UID:{uid}@subtrack.local", "DTSTAMP:" + stamp,
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{start + timedelta(days=1):%Y%m%d}",
            "SUMMARY:" + escape_text(f"Renewal: {item.name}"),
            "DESCRIPTION:" + escape_text(
                f"Expected renewal date; not proof of payment. Check or cancel with the provider. "
                f"All-day date from your AllOutFree settings ({zone}). This is a one-time snapshot; "
                "choose notifications in your calendar and export again after changes."
            ),
            "TRANSP:TRANSPARENT", "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8")


def download(items):
    zone = user_zone(current_user.timezone).key
    response = Response(calendar_bytes(items, current_user.id, zone), content_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="alloutfree-renewals.ics"'
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@bp.route("/")
@login_required
def index():
    items = own_active().order_by(Subscription.next_renewal_at, Subscription.id).all()
    today = local_now(current_user.timezone).date()
    return render_template("calendar/index.html", items=items, zone=user_zone(current_user.timezone).key,
                           months=month_grids(items, today), today=today)


def month_grids(items, today: date, count: int = 2) -> list[dict]:
    """This month and the next one as weeks of days (Monday first), each day
    with the plans that renew on it, for the picture at the top of the page."""
    by_day = defaultdict(list)
    for item in items:
        by_day[item.next_renewal_at].append(item)
    months, first = [], today.replace(day=1)
    for _ in range(count):
        weeks = [[{"day": d, "inside": d.month == first.month, "plans": by_day.get(d, [])} for d in week]
                 for week in MonthCalendar(firstweekday=0).monthdatescalendar(first.year, first.month)]
        months.append({"first": first, "weeks": weeks})
        first = (first + timedelta(days=32)).replace(day=1)
    return months


@bp.route("/renewals.ics")
@login_required
def export_all():
    return download(own_active().order_by(Subscription.next_renewal_at, Subscription.id).all())


@bp.route("/subscriptions/<int:item_id>")
@login_required
def review(item_id):
    item = own_item(item_id)
    zone = user_zone(current_user.timezone).key
    response = Response(render_template("calendar/review.html", item=item, zone=zone,
                                        google_url=google_link(item, zone)))
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.route("/subscriptions/<int:item_id>.ics")
@login_required
def export_one(item_id):
    return download([own_item(item_id)])
