"""Sign in with Google / GitHub. Google and GitHub are faked: no real network."""

from urllib.parse import parse_qs, urlparse

import pytest

from app import oauth
from app.models import User
from tests.conftest import PASSWORD, sign_up


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture()
def providers_on(monkeypatch):
    for name in ["GOOGLE", "GITHUB"]:
        monkeypatch.setenv(f"{name}_CLIENT_ID", f"{name.lower()}-id")
        monkeypatch.setenv(f"{name}_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("SITE_URL", "https://example.com")


def start_and_get_state(client, provider):
    res = client.get(f"/auth/{provider}")
    assert res.status_code == 302
    return parse_qs(urlparse(res.headers["Location"]).query)


def fake_provider(monkeypatch, email_data):
    monkeypatch.setattr(oauth.requests, "post", lambda *a, **k: FakeResponse({"access_token": "tok"}))
    monkeypatch.setattr(oauth.requests, "get", lambda *a, **k: FakeResponse(email_data))


def test_buttons_hidden_until_set_up(client, monkeypatch):
    for name in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"]:
        monkeypatch.delenv(name, raising=False)
    assert "Continue with" not in client.get("/login").get_data(as_text=True)
    assert client.get("/auth/google").status_code == 404


def test_buttons_show_when_set_up(client, providers_on):
    page = client.get("/register").get_data(as_text=True)
    assert "Continue with Google" in page
    assert "Continue with GitHub" in page


def test_start_sends_user_to_google_with_state(client, providers_on):
    params = start_and_get_state(client, "google")
    assert params["client_id"] == ["google-id"]
    assert params["redirect_uri"] == ["https://example.com/auth/google/callback"]
    assert params["state"][0]


def test_wrong_state_is_refused(client, app, providers_on, monkeypatch):
    start_and_get_state(client, "google")
    fake_provider(monkeypatch, {"email": "a@gmail.com", "email_verified": True})
    res = client.get("/auth/google/callback?code=abc&state=wrong")
    assert res.headers["Location"].endswith("/login")
    with app.app_context():
        assert User.query.count() == 0


def test_google_sign_in_creates_account(client, app, providers_on, monkeypatch):
    state = start_and_get_state(client, "google")["state"][0]
    fake_provider(monkeypatch, {"email": "Person@Gmail.com", "email_verified": True})
    res = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert res.headers["Location"].endswith("/subscriptions/")
    with app.app_context():
        assert User.query.filter_by(email="person@gmail.com").count() == 1


def test_unverified_google_email_is_refused(client, app, providers_on, monkeypatch):
    state = start_and_get_state(client, "google")["state"][0]
    fake_provider(monkeypatch, {"email": "x@gmail.com", "email_verified": False})
    res = client.get(f"/auth/google/callback?code=abc&state={state}")
    assert res.headers["Location"].endswith("/login")
    with app.app_context():
        assert User.query.count() == 0


def test_github_uses_primary_verified_email(client, app, providers_on, monkeypatch):
    state = start_and_get_state(client, "github")["state"][0]
    fake_provider(
        monkeypatch,
        [
            {"email": "old@example.com", "primary": False, "verified": True},
            {"email": "main@example.com", "primary": True, "verified": True},
        ],
    )
    client.get(f"/auth/github/callback?code=abc&state={state}")
    with app.app_context():
        assert User.query.filter_by(email="main@example.com").count() == 1


def google_login(client, monkeypatch, email, next_url=""):
    query = f"?next={next_url}" if next_url else ""
    state = parse_qs(urlparse(client.get(f"/auth/google{query}").headers["Location"]).query)["state"][0]
    fake_provider(monkeypatch, {"email": email, "email_verified": True})
    return client.get(f"/auth/google/callback?code=abc&state={state}")


def test_existing_email_logs_into_same_account(client, app, providers_on, monkeypatch):
    sign_up(client, "me@gmail.com")
    client.post("/logout")
    google_login(client, monkeypatch, "me@gmail.com")
    with app.app_context():
        assert User.query.count() == 1
    assert client.get("/subscriptions/").status_code == 200


def test_google_users_get_a_username_and_are_confirmed(client, app, providers_on, monkeypatch):
    google_login(client, monkeypatch, "Toan.Bui@gmail.com")
    with app.app_context():
        user = User.query.one()
        assert user.username == "toanbui"
        assert user.email_verified
        assert not user.is_admin


def test_unconfirmed_password_account_is_taken_back_by_the_real_owner(client, app, providers_on, monkeypatch):
    # An attacker signs up first with the victim's email and a password they know.
    sign_up(client, "victim@gmail.com")
    client.post("/logout")
    # The real owner arrives with Google, which proves they own the email.
    google_login(client, monkeypatch, "victim@gmail.com")
    with app.app_context():
        user = User.query.one()
        assert user.email_verified
        assert not user.check_password(PASSWORD)  # the attacker's password no longer works


def test_confirmed_account_keeps_its_password(client, app, providers_on, monkeypatch):
    sign_up(client, "me@gmail.com")
    with app.app_context():
        user = User.query.one()
        user.email_verified_at = user.created_at
        from app import db

        db.session.commit()
    client.post("/logout")
    google_login(client, monkeypatch, "me@gmail.com")
    with app.app_context():
        assert User.query.one().check_password(PASSWORD)


def test_oauth_keeps_a_safe_next_page(client, providers_on, monkeypatch):
    assert google_login(client, monkeypatch, "a@gmail.com", "/links/").headers["Location"] == "/links/"
    client.post("/logout")
    res = google_login(client, monkeypatch, "a@gmail.com", "https://evil.example")
    assert res.headers["Location"].endswith("/subscriptions/")
