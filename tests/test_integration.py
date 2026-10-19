"""Real Flask requests and database writes, with synthetic accounts only."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Link, ReminderLog, Subscription, User
from tests.conftest import sign_up


PASSWORD = "DemoOnly!2026"


def subscription_form(**changes):
    return {
        "name": "Demo streaming", "amount": "12.34", "currency": "USD",
        "cycle": "monthly", "next_renewal_at": "2028-02-29",
        "remind_days": "3", "notes": "Synthetic example",
        **changes,
    }


def test_signup_login_subscription_edit_and_archive(client, app):
    assert sign_up(client, password=PASSWORD).status_code == 302
    client.post("/logout")
    assert client.get("/subscriptions/").status_code == 302
    assert client.post("/login", data={
        "email": "a@example.com", "password": PASSWORD,
    }).status_code == 302
    assert client.post("/subscriptions/new", data=subscription_form()).status_code == 302
    with app.app_context():
        item = Subscription.query.one()
        item_id = item.id
        assert item.amount == Decimal("12.34")
        assert item.next_renewal_at == date(2028, 2, 29)
        assert item.user_id == User.query.one().id
    assert b"Demo streaming" in client.get("/subscriptions/").data
    assert client.post(f"/subscriptions/{item_id}/edit", data=subscription_form(
        name="Annual demo", cycle="yearly", amount="99.90",
    )).status_code == 302
    with app.app_context():
        item = db.session.get(Subscription, item_id)
        assert (item.name, item.cycle, item.amount) == ("Annual demo", "yearly", Decimal("99.90"))
    assert client.post(f"/subscriptions/{item_id}/archive").status_code == 302
    assert b"Annual demo" not in client.get("/subscriptions/").data
    with app.app_context():
        assert db.session.get(Subscription, item_id).status == "archived"


@pytest.mark.parametrize("method,path", [
    ("get", "/subscriptions/"), ("get", "/subscriptions/new"),
    ("post", "/subscriptions/new"), ("get", "/subscriptions/1/edit"),
    ("post", "/subscriptions/1/edit"), ("post", "/subscriptions/1/archive"),
    ("get", "/links/"), ("post", "/links/new"),
    ("post", "/links/preview"), ("post", "/links/1/pin"),
    ("post", "/links/1/delete"), ("get", "/admin/users"),
])
def test_private_routes_require_login(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_two_users_cannot_read_or_change_each_others_subscriptions(app):
    owner, other = app.test_client(), app.test_client()
    sign_up(owner, "owner@example.com", PASSWORD)
    sign_up(other, "other@example.com", PASSWORD)
    owner.post("/subscriptions/new", data=subscription_form())
    with app.app_context():
        item_id = Subscription.query.one().id
        owner_id = User.query.filter_by(email="owner@example.com").one().id
    assert b"Demo streaming" not in other.get("/subscriptions/").data
    assert other.get(f"/subscriptions/{item_id}/edit").status_code == 404
    assert other.post(f"/subscriptions/{item_id}/edit", data=subscription_form(
        name="Changed by someone else",
    )).status_code == 404
    assert other.post(f"/subscriptions/{item_id}/archive").status_code == 404
    with app.app_context():
        item = db.session.get(Subscription, item_id)
        assert (item.user_id, item.name, item.status) == (owner_id, "Demo streaming", "active")
    assert other.get("/admin/users").status_code == 403


def test_link_search_and_tags_never_include_another_users_data(app):
    owner, other = app.test_client(), app.test_client()
    sign_up(owner, "owner@example.com", PASSWORD)
    sign_up(other, "other@example.com", PASSWORD)
    owner.post("/links/new", data={
        "url": "https://example.com/private", "title": "Owner private billing",
        "tags": "owner-private-tag", "notes": "Owner private notes",
    })
    for path in ("/links/", "/links/?q=private", "/links/?tag=owner-private-tag"):
        page = other.get(path).get_data(as_text=True)
        assert "Owner private billing" not in page
        # The filter input may echo a tag supplied in this request; chips must not leak it.
        assert ">owner-private-tag</a>" not in page
        assert "Owner private notes" not in page
    with app.app_context():
        link_id = Link.query.one().id
    assert other.post(f"/links/{link_id}/edit", data={
        "url": "https://example.com/changed", "title": "Changed",
    }).status_code == 404
    with app.app_context():
        assert db.session.get(Link, link_id).title == "Owner private billing"


def test_user_text_is_escaped_in_subscription_and_link_pages(client):
    sign_up(client, password=PASSWORD)
    payload = '<script>alert("demo")</script>'
    client.post("/subscriptions/new", data=subscription_form(name=payload))
    client.post("/links/new", data={"url": "https://example.com", "title": payload})
    for path in ("/subscriptions/", "/links/"):
        page = client.get(path).get_data(as_text=True)
        assert payload not in page
        assert "&lt;script&gt;" in page


def test_sqlite_rejects_duplicate_reminder_log_but_keeps_distinct_renewals(client, app):
    """Database uniqueness only: this does not exercise an email sender or retry job."""
    sign_up(client, password=PASSWORD)
    client.post("/subscriptions/new", data=subscription_form())
    with app.app_context():
        item_id = Subscription.query.one().id

        def log(day, channel="email"):
            return ReminderLog(subscription_id=item_id, renewal_date=day, channel=channel)

        db.session.add(log(date(2028, 2, 29)))
        db.session.commit()
        db.session.add(log(date(2028, 2, 29)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        db.session.add_all([log(date(2028, 3, 29)), log(date(2028, 2, 29), "browser")])
        db.session.commit()
        assert ReminderLog.query.count() == 3
