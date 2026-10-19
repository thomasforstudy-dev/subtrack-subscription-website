"""Subscriptions: each user only ever sees and changes their own."""

from app.models import Subscription
from tests.conftest import sign_up


def add(client, name="Netflix"):
    return client.post(
        "/subscriptions/new",
        data={"name": name, "amount": "9.99", "currency": "usd", "cycle": "monthly",
              "next_renewal_at": "2026-11-01", "remind_days": "7"},
    )


def test_other_users_cannot_see_or_change_my_subscriptions(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    add(me, "My secret plan")
    with app.app_context():
        item_id = Subscription.query.one().id

    assert b"My secret plan" not in other.get("/subscriptions/").data
    assert other.get(f"/subscriptions/{item_id}/edit").status_code == 404
    assert other.post(f"/subscriptions/{item_id}/edit", data={"name": "Hacked"}).status_code == 404
    assert other.post(f"/subscriptions/{item_id}/archive").status_code == 404
    with app.app_context():
        item = Subscription.query.one()
        assert item.name == "My secret plan" and item.status == "active"


def test_a_user_id_sent_in_the_form_is_ignored(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    with app.app_context():
        from app.models import User

        my_id = User.query.filter_by(email="me@example.com").one().id
    # "other" tries to create a subscription in my account.
    other.post("/subscriptions/new", data={"name": "Planted", "user_id": str(my_id)})
    with app.app_context():
        assert Subscription.query.one().user_id != my_id
