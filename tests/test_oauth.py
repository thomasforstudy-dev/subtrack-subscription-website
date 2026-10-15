"""Sign in with Google / GitHub. Google and GitHub are faked: no real network."""

from urllib.parse import parse_qs, urlparse

import pytest

from app import oauth
from app.models import User


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


def test_existing_email_logs_into_same_account(client, app, providers_on, monkeypatch):
    client.post("/register", data={"email": "me@gmail.com", "password": "password123", "confirm": "password123"})
    client.get("/logout")
    state = start_and_get_state(client, "google")["state"][0]
    fake_provider(monkeypatch, {"email": "me@gmail.com", "email_verified": True})
    client.get(f"/auth/google/callback?code=abc&state={state}")
    with app.app_context():
        assert User.query.count() == 1
    assert client.get("/subscriptions/").status_code == 200
