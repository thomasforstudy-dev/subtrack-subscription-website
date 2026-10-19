"""Subscriptions: checking the form, list tools, and each user only ever sees their own."""

from decimal import Decimal

import pytest

from app.models import Renewal, Subscription, User
from tests.conftest import sign_up

GOOD = {
    "name": "Netflix", "amount": "9.99", "currency": "usd", "cycle": "monthly",
    "next_renewal_at": "2026-11-01", "lead_days": "14, 7,3",
}


def add(client, **fields):
    return client.post("/subscriptions/new", data={**GOOD, **fields})


# ---------- the form ---------------------------------------------------------

def test_saves_clean_values(user, app):
    add(user, manage_url="netflix.com/cancel")
    with app.app_context():
        item = Subscription.query.one()
        assert item.amount == Decimal("9.99")
        assert item.currency == "USD"
        assert item.lead_days == "14,7,3"
        assert item.remind_days == 14  # biggest lead, for older pages
        assert item.billing_day == 1
        assert item.manage_url == "https://netflix.com/cancel"


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("name", "", "give it a name"),
        ("amount", "9.999", "price as a number"),
        ("amount", "-1", "price as a number"),
        ("amount", "1,5", "price as a number"),
        ("amount", "NaN", "price as a number"),
        ("amount", "100000000", "price as a number"),
        ("currency", "US", "3-letter currency"),
        ("currency", "U$D", "3-letter currency"),
        ("cycle", "daily", "weekly, monthly or yearly"),
        ("next_renewal_at", "", "next renewal date"),
        ("next_renewal_at", "31/12/2026", "next renewal date"),
        ("next_renewal_at", "1999-12-31", "check the year"),
        ("lead_days", "14,7,3,1", "up to 3"),
        ("lead_days", "400", "up to 3"),
        ("lead_days", "-1", "up to 3"),
        ("manage_url", "javascript:alert(1)", "Manage link"),
    ],
)
def test_refuses_bad_values_and_keeps_what_was_typed(user, app, field, value, message):
    res = add(user, **{field: value}, notes="keep me")
    page = res.get_data(as_text=True)
    assert message in page
    assert "keep me" in page  # the form is shown again with the typed values
    with app.app_context():
        assert Subscription.query.count() == 0


def test_old_forms_with_remind_days_still_work(user, app):
    data = {k: v for k, v in GOOD.items() if k != "lead_days"}
    user.post("/subscriptions/new", data={**data, "remind_days": "5"})
    with app.app_context():
        assert Subscription.query.one().lead_days == "5"


def test_editing_an_archived_one_keeps_it_archived(user, app):
    add(user)
    with app.app_context():
        item_id = Subscription.query.one().id
    user.post(f"/subscriptions/{item_id}/archive")
    user.post(f"/subscriptions/{item_id}/edit", data=GOOD)
    with app.app_context():
        assert Subscription.query.one().status == "archived"
    user.post(f"/subscriptions/{item_id}/restore")
    with app.app_context():
        assert Subscription.query.one().status == "active"


# ---------- list: search, filter, sort, pages --------------------------------

def test_search_filter_sort(user):
    # (Not "Netflix": Subby's panel on every page mentions it.)
    add(user, name="Hulu", amount="9.99", next_renewal_at="2026-11-05")
    add(user, name="Spotify", amount="5.00", next_renewal_at="2026-11-01", notes="family plan")
    add(user, name="Adobe", amount="20.00", next_renewal_at="2026-12-01")

    page = user.get("/subscriptions/?q=family").get_data(as_text=True)
    assert "Spotify" in page and "Hulu" not in page

    page = user.get("/subscriptions/?sort=amount").get_data(as_text=True)
    assert page.index("Adobe") < page.index("Hulu") < page.index("Spotify")

    page = user.get("/subscriptions/").get_data(as_text=True)  # soonest first
    assert page.index("Spotify") < page.index("Hulu") < page.index("Adobe")


def test_archived_filter(user, app):
    add(user, name="Old gym")
    with app.app_context():
        item_id = Subscription.query.one().id
    user.post(f"/subscriptions/{item_id}/archive")
    assert "Old gym" not in user.get("/subscriptions/").get_data(as_text=True)
    assert "Old gym" in user.get("/subscriptions/?status=archived").get_data(as_text=True)


def test_pages_of_twenty(user):
    for n in range(25):
        add(user, name=f"Plan {n:02d}", next_renewal_at=f"2026-11-{n + 1:02d}")
    first = user.get("/subscriptions/").get_data(as_text=True)
    second = user.get("/subscriptions/?page=2").get_data(as_text=True)
    assert "Plan 00" in first and "Plan 24" not in first
    assert "Plan 24" in second and "Page 2 of 2" in second


# ---------- privacy ----------------------------------------------------------

def test_other_users_cannot_see_or_change_my_subscriptions(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    add(me, name="My secret plan")
    with app.app_context():
        item_id = Subscription.query.one().id

    assert b"My secret plan" not in other.get("/subscriptions/?status=all").data
    assert other.get(f"/subscriptions/{item_id}/edit").status_code == 404
    assert other.post(f"/subscriptions/{item_id}/edit", data={**GOOD, "name": "Hacked"}).status_code == 404
    assert other.post(f"/subscriptions/{item_id}/archive").status_code == 404
    assert other.post(f"/subscriptions/{item_id}/restore").status_code == 404
    with app.app_context():
        item = Subscription.query.one()
        assert item.name == "My secret plan" and item.status == "active"


def test_a_user_id_sent_in_the_form_is_ignored(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    with app.app_context():
        my_id = User.query.filter_by(email="me@example.com").one().id
    # "other" tries to create a subscription in my account.
    add(other, name="Planted", user_id=str(my_id))
    with app.app_context():
        assert Subscription.query.one().user_id != my_id


def test_cannot_mark_someone_elses_renewal(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    add(me)
    with app.app_context():
        from app import db

        sub = Subscription.query.one()
        db.session.add(Renewal(subscription_id=sub.id, user_id=sub.user_id,
                               due_date=sub.next_renewal_at, amount=sub.amount, currency="USD"))
        db.session.commit()
        renewal_id = Renewal.query.one().id
    assert other.post(f"/subscriptions/renewals/{renewal_id}", data={"status": "paid"}).status_code == 404
    assert me.post(f"/subscriptions/renewals/{renewal_id}", data={"status": "paid"}).status_code == 302
    with app.app_context():
        assert Renewal.query.one().status == "paid"
