"""Original four review contracts, fixed by Claude and verified on the merged UI."""

from app.models import User
from tests.conftest import sign_up
from tests.test_integration import PASSWORD, subscription_form


def test_public_signup_does_not_grant_admin(client, app):
    sign_up(client, password=PASSWORD)
    with app.app_context():
        assert User.query.one().is_admin is False


def test_subscription_post_without_csrf_is_refused(client):
    sign_up(client, password=PASSWORD)
    response = client.post("/subscriptions/new", data=subscription_form(), csrf=False)
    assert response.status_code in (400, 403)


def test_invalid_renewal_date_returns_a_form_error(client):
    sign_up(client, password=PASSWORD)
    response = client.post("/subscriptions/new", data=subscription_form(next_renewal_at="2026-02-30"))
    assert response.status_code in (200, 400)


def test_weak_password_cannot_create_new_account(client, app):
    sign_up(client, password="password123")
    with app.app_context():
        assert User.query.count() == 0
