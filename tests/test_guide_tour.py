"""The user guide, the guided tours, the new Settings tools and the calendar picture."""

import json
import re
from datetime import timedelta

from app import mailer
from app.models import User, utcnow
from app.schedule import local_now



def tour_data(page):
    found = re.search(r'<script type="application/json" id="tour-data">(.*?)</script>', page, re.S)
    return json.loads(found.group(1)) if found else None


def test_guide_page_for_visitors_and_members(app, user):
    page = app.test_client().get("/guide").get_data(as_text=True)
    assert "AllOutFree in 8 steps" in page and "/register?tour=1" in page
    assert tour_data(page) is None  # visitors get no app tour
    page = user.get("/guide").get_data(as_text=True)
    assert 'data-tour-start="0"' in page and tour_data(page)["name"] == "app"


def test_every_tour_target_exists_on_its_page(app, user):
    data = tour_data(user.get("/dashboard").get_data(as_text=True))
    assert data["user"] and len(data["steps"]) >= 8
    for step in data["steps"]:
        if not step["target"]:
            continue
        marker = step["target"].replace("[data-tour=", 'data-tour="').replace("]", '"')
        page = user.get(step["path"] or "/dashboard").get_data(as_text=True)
        assert marker in page, step


def test_new_accounts_start_the_tour_but_not_after_adding_a_plan(user):
    assert "data-tour-autostart" in user.get("/dashboard").get_data(as_text=True)
    user.post("/subscriptions/new", data={"name": "Netflix", "amount": "9", "currency": "USD", "cycle": "monthly",
                                          "next_renewal_at": "2026-12-01", "lead_days": "7"})
    assert "data-tour-autostart" not in user.get("/dashboard").get_data(as_text=True)


def test_signup_tour_on_the_register_page(client):
    page = client.get("/register").get_data(as_text=True)
    data = tour_data(page)
    assert data["name"] == "signup"
    for marker in ("email", "username", "password", "create"):
        assert f'data-tour="{marker}"' in page
    assert data["steps"][0]["optional"] is True  # Google/GitHub may be switched off


def test_test_email_needs_a_confirmed_email_and_is_limited(app, user):
    before = len(mailer.sent)  # the sign-up code email
    page = user.post("/settings/test-email", follow_redirects=True).get_data(as_text=True)
    assert "Confirm your email first" in page and len(mailer.sent) == before
    with app.app_context():
        me = User.query.one()
        me.email_verified_at = utcnow()
        from app import db
        db.session.commit()
    for _ in range(3):
        page = user.post("/settings/test-email", follow_redirects=True).get_data(as_text=True)
        assert "Test email sent" in page
    assert len(mailer.sent) == before + 3 and mailer.sent[-1].subject.startswith("Test:")
    assert mailer.sent[-1].to == "a@example.com"  # only ever to your own address
    page = user.post("/settings/test-email", follow_redirects=True).get_data(as_text=True)
    assert "try again in an hour" in page and len(mailer.sent) == before + 3


def test_settings_page_keeps_the_form_fields(user):
    page = user.get("/settings").get_data(as_text=True)
    for name in ('name="timezone"', 'name="reminder_hour"', 'name="reminders_enabled"', 'name="channels"'):
        assert name in page
    assert 'data-set-hour="9"' in page and 'data-set-lang="en"' in page


def test_calendar_shows_renewals_on_the_month_grid(app, user):
    with app.app_context():
        today = local_now(User.query.one().timezone).date()
    soon = today + timedelta(days=1)
    user.post("/subscriptions/new", data={"name": "Gridflix", "amount": "9", "currency": "USD", "cycle": "monthly",
                                          "next_renewal_at": soon.isoformat(), "lead_days": "7"})
    page = user.get("/calendar/").get_data(as_text=True)
    assert 'title="Gridflix"' in page and "month-day" in page and " today" in page

