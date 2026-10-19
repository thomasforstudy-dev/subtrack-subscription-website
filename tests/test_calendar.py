"""Manual calendar exports: user scope, all-day dates, privacy and RFC escaping."""

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from app import db
from app.calendar import calendar_bytes, google_link
from app.models import Subscription, User
from tests.conftest import sign_up
from tests.test_review_repairs import FULL


def add_item(client, app, **changes):
    assert client.post("/subscriptions/new", data={**FULL, **changes}).status_code == 302
    with app.app_context():
        return Subscription.query.order_by(Subscription.id.desc()).first().id


def unfolded(response):
    return response.data.decode("utf-8").replace("\r\n ", "")


@pytest.mark.parametrize("path", ["/calendar/", "/calendar/renewals.ics", "/calendar/subscriptions/1", "/calendar/subscriptions/1.ics"])
def test_calendar_routes_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_download_uses_all_day_leap_date_and_exclusive_end(user, app):
    item_id = add_item(user, app, next_renewal_at="2028-02-29")
    response = user.get(f"/calendar/subscriptions/{item_id}.ics")
    text = unfolded(response)
    assert "DTSTART;VALUE=DATE:20280229\r\n" in text
    assert "DTEND;VALUE=DATE:20280301\r\n" in text
    assert "DTSTART;TZID=" not in text  # RFC DATE values have no TZID parameter
    assert response.mimetype == "text/calendar"
    assert response.headers["Content-Disposition"] == 'attachment; filename="subtrack-renewals.ics"'
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.data.endswith(b"END:VCALENDAR\r\n")


def test_uid_stays_stable_after_a_subscription_edit(user, app):
    item_id = add_item(user, app)
    first = unfolded(user.get(f"/calendar/subscriptions/{item_id}.ics"))
    user.post(f"/subscriptions/{item_id}/edit", data={**FULL, "name": "Changed", "next_renewal_at": "2028-02-29"})
    second = unfolded(user.get(f"/calendar/subscriptions/{item_id}.ics"))
    uid = lambda text: next(line for line in text.split("\r\n") if line.startswith("UID:"))
    assert uid(first) == uid(second)
    assert "SUMMARY:Renewal: Changed" in second


def test_other_users_cannot_review_or_download_my_events(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "owner@example.com")
    sign_up(other, "other@example.com")
    item_id = add_item(me, app, name="Owner private calendar item")
    for suffix in ("", ".ics"):
        assert other.get(f"/calendar/subscriptions/{item_id}{suffix}").status_code == 404
    assert b"Owner private calendar item" not in other.get("/calendar/renewals.ics").data
    assert b"Owner private calendar item" not in other.get("/calendar/").data


def test_export_all_includes_every_active_page_but_not_archived(user, app):
    for number in range(25):
        add_item(user, app, name=f"Calendar fixture {number:02d}")
    last = add_item(user, app, name="Archived calendar fixture")
    user.post(f"/subscriptions/{last}/archive")
    text = unfolded(user.get("/calendar/renewals.ics"))
    assert text.count("BEGIN:VEVENT\r\n") == 25
    assert "Calendar fixture 24" in text
    assert "Archived calendar fixture" not in text
    assert user.get(f"/calendar/subscriptions/{last}.ics").status_code == 404


def test_empty_export_is_a_valid_empty_calendar(user):
    text = unfolded(user.get("/calendar/renewals.ics"))
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.endswith("END:VCALENDAR\r\n")
    assert "BEGIN:VEVENT" not in text


def test_google_link_and_ics_omit_private_fields(user, app):
    item_id = add_item(user, app, name="Private title & action=DELETE", notes="PRIVATE-NOTE-DO-NOT-EXPORT",
                       manage_url="https://example.com/private-manage-token")
    with app.app_context():
        item = db.session.get(Subscription, item_id)
        link = google_link(item, "Asia/Ho_Chi_Minh")
    parsed = urlsplit(link)
    values = parse_qs(parsed.query)
    assert (parsed.scheme, parsed.netloc, parsed.path) == ("https", "calendar.google.com", "/calendar/render")
    assert set(values) == {"action", "text", "dates", "ctz"}
    assert values["action"] == ["TEMPLATE"]
    assert values["text"] == ["Renewal: Private title & action=DELETE"]
    assert values["ctz"] == ["Asia/Ho_Chi_Minh"]
    text = unfolded(user.get(f"/calendar/subscriptions/{item_id}.ics"))
    for private in ("PRIVATE-NOTE-DO-NOT-EXPORT", "private-manage-token", "a@example.com", "10.00"):
        assert private not in link and private not in text
    review = user.get(f"/calendar/subscriptions/{item_id}").get_data(as_text=True)
    assert "Nothing is added until you review" in review
    assert 'referrerpolicy="no-referrer"' in review


@pytest.mark.parametrize("zone", ["Asia/Ho_Chi_Minh", "America/New_York", "Pacific/Auckland"])
def test_account_timezone_does_not_shift_an_all_day_date(user, app, zone):
    item_id = add_item(user, app, next_renewal_at="2026-11-01")
    with app.app_context():
        owner = User.query.one()
        owner.timezone = zone
        db.session.commit()
    text = unfolded(user.get(f"/calendar/subscriptions/{item_id}.ics"))
    assert f"X-WR-TIMEZONE:{zone}" in text
    assert "DTSTART;VALUE=DATE:20261101" in text


def test_ics_injection_and_utf8_folding_do_not_create_extra_components():
    # Construct only in memory: this intentionally exceeds normal name length.
    item = Subscription(id=9, name="Tiếng Việt ☁ " * 20 + "\\;,\r\nBEGIN:VEVENT\r\nX-ATTACK:YES\x00",
                        next_renewal_at=date(2028, 2, 29))
    data = calendar_bytes([item], 4, "UTC")
    assert all(len(line) <= 75 for line in data.split(b"\r\n"))
    assert all(line.decode("utf-8") is not None for line in data.split(b"\r\n"))
    text = data.decode("utf-8").replace("\r\n ", "")
    assert text.count("\r\nBEGIN:VEVENT\r\n") == 1
    assert "\r\nX-ATTACK:" not in text
    assert "\\nBEGIN:VEVENT\\nX-ATTACK:YES" in text
    assert "\\\\\\;\\," in text
    assert "\x00" not in text
