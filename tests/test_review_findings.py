"""Unresolved contracts owned by Claude; strict xfail makes fixes visible in CI.

See docs/reviews/2026-10-19-quality-baseline.md before removing a marker.
"""

import pytest

from app.models import User
from tests.conftest import sign_up
from tests.test_integration import PASSWORD, subscription_form


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R1: first public signup becomes admin; Claude")
def test_public_signup_does_not_grant_admin(client, app):
    sign_up(client, password=PASSWORD)
    with app.app_context():
        assert User.query.one().is_admin is False


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R2: mutation forms lack server CSRF validation; Claude")
def test_subscription_post_without_csrf_is_refused(client):
    sign_up(client, password=PASSWORD)
    response = client.post("/subscriptions/new", data=subscription_form())
    assert response.status_code in (400, 403)


@pytest.mark.xfail(strict=True, reason="R5: invalid renewal date raises ValueError; Claude", raises=ValueError)
def test_invalid_renewal_date_returns_a_form_error(client):
    sign_up(client, password=PASSWORD)
    response = client.post("/subscriptions/new", data=subscription_form(next_renewal_at="2026-02-30"))
    assert response.status_code in (200, 400)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R6: signup lacks uppercase/special-character policy; Claude")
def test_weak_password_cannot_create_new_account(client, app):
    sign_up(client, password="password123")
    with app.app_context():
        assert User.query.count() == 0
