"""Shared test setup: every test gets a fresh, empty test database."""

import os

import pytest
from flask.testing import FlaskClient

# Never touch SQL Server, real email or your real .env values while testing.
os.environ["DB_SERVER"] = ""
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-1234"
os.environ["MAIL_BACKEND"] = "memory"
os.environ["RESEND_API_KEY"] = ""

PASSWORD = "Password123!"  # meets the sign-up rules


class CSRFClient(FlaskClient):
    """A test browser that puts the CSRF token in its forms, like our pages do.

    The server still checks the token for real. Pass csrf=False to send a
    form without it (to test that it is refused).
    """

    def csrf_token(self) -> str:
        from app.security import CSRF_FIELD

        with self.session_transaction() as sess:
            if CSRF_FIELD not in sess:
                sess[CSRF_FIELD] = "test-csrf-token"
            return sess[CSRF_FIELD]

    def post(self, *args, csrf=True, **kwargs):
        if csrf and "json" not in kwargs:
            data = dict(kwargs.get("data") or {})
            data.setdefault("csrf_token", self.csrf_token())
            kwargs["data"] = data
        return super().post(*args, **kwargs)


@pytest.fixture(autouse=True)
def fresh_limits_and_mail():
    from app import mailer
    from app.security import clear_all_limits

    clear_all_limits()
    mailer.sent.clear()
    yield


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    app.test_client_class = CSRFClient
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def sign_up(client, email="a@example.com", password=PASSWORD, username=None):
    # "a@example.com" -> "a_user" (usernames need at least 3 characters)
    username = username or email.split("@")[0].replace(".", "_") + "_user"
    return client.post(
        "/register",
        data={"username": username, "email": email, "password": password, "confirm": password},
    )


@pytest.fixture()
def user(client):
    sign_up(client)
    return client
