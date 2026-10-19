"""Dashboard totals and the settings page."""

from datetime import timedelta

from app.schedule import local_now
from tests.conftest import sign_up


def add(client, name, amount, currency, cycle="monthly", days=5):
    # "Today" where a new user lives (UTC until they pick a time zone), like the
    # app counts it. date.today() is the PC's date: between midnight and 7 am in
    # Vietnam it is a day ahead of UTC, which made days_left off by one.
    today = local_now("UTC").date()
    client.post("/subscriptions/new", data={
        "name": name, "amount": amount, "currency": currency, "cycle": cycle,
        "next_renewal_at": (today + timedelta(days=days)).isoformat(), "lead_days": "7",
    })


def test_totals_are_per_currency_and_never_mixed(user):
    add(user, "Netflix", "10.00", "USD")
    add(user, "Domain", "120.00", "USD", cycle="yearly")
    add(user, "Zing", "50000", "VND")
    data = user.get("/dashboard.json").get_json()
    projected = {row["currency"]: row for row in data["projected"]}
    assert projected["USD"]["monthly"] == "20.00"  # 10 + 120/12
    assert projected["USD"]["yearly"] == "240.00"
    assert projected["VND"]["monthly"] == "50000.00"
    assert len(projected) == 2


def test_upcoming_lists_the_next_30_days(user):
    add(user, "Soon", "1.00", "USD", days=3)
    add(user, "Later", "1.00", "USD", days=45)
    data = user.get("/dashboard.json").get_json()
    assert [s["name"] for s in data["upcoming"]] == ["Soon"]
    assert data["upcoming"][0]["days_left"] == 3
    assert data["upcoming"][0]["amount"] == "1.00"  # money as text, no float rounding


def test_dashboard_page_and_privacy(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    add(me, "My secret plan", "9.99", "USD")
    assert "My secret plan" in me.get("/dashboard").get_data(as_text=True)
    assert "My secret plan" not in other.get("/dashboard").get_data(as_text=True)
    assert other.get("/dashboard.json").get_json()["upcoming"] == []


def test_dashboard_needs_login(client):
    assert client.get("/dashboard").status_code == 302
    assert client.get("/dashboard.json").status_code == 302


def test_settings_save_and_validate(user, app):
    res = user.post("/settings", data={"timezone": "Asia/Ho_Chi_Minh", "reminder_hour": "8",
                                       "channels": "email"})
    assert res.status_code == 302
    from app.models import User

    with app.app_context():
        me = User.query.one()
        assert me.timezone == "Asia/Ho_Chi_Minh"
        assert me.reminder_hour == 8
        assert me.reminders_enabled is False  # box not ticked = off
        assert me.channel_list == ["email"]

    page = user.post("/settings", data={"timezone": "Mars/Base", "reminder_hour": "8"}).get_data(as_text=True)
    assert "pick a time zone" in page
    page = user.post("/settings", data={"timezone": "UTC", "reminder_hour": "24"}).get_data(as_text=True)
    assert "0 to 23" in page


def test_unknown_channels_are_ignored(user, app):
    user.post("/settings", data={"timezone": "UTC", "reminder_hour": "9", "reminders_enabled": "on",
                                 "channels": ["email", "sms"]})
    from app.models import User

    with app.app_context():
        assert User.query.one().channel_list == ["email"]
