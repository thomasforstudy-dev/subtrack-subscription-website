"""Shared test setup: every test gets a fresh, empty test database."""

import ipaddress
import os
import socket

import pytest
from flask.testing import FlaskClient

# Never touch SQL Server, real email or your real .env values while testing.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DB_SERVER"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-1234"
os.environ["MAIL_BACKEND"] = "memory"
os.environ["RESEND_API_KEY"] = ""
for name in (
    "DB_USER", "DB_PASSWORD", "GEMINI_API_KEY", "GEMINI_MODEL",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET", "SITE_URL", "MESSENGER_URL", "ZALO_URL",
    "PHI_API_KEY", "PHI_API_URL", "SUBBY_FALLBACK", "MAIL_FROM",
):
    os.environ.pop(name, None)
os.environ["SUBBY_PROVIDER"] = "fake"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # The pinned dotenv 1.1.1 predates its disable environment flag.
    patcher = pytest.MonkeyPatch()
    patcher.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    config.add_cleanup(patcher.undo)


@pytest.fixture(autouse=True)
def local_network_only(monkeypatch):
    real_connect = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            try:
                local = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                local = False
            if not local:
                raise OSError("Tests must mock external network connections.")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setenv("NO_PROXY", "*")

PASSWORD = "Password123!"  # meets the sign-up rules


class CSRFClient(FlaskClient):
    """A test browser that puts the CSRF token in its forms, like our pages do.

    The server still checks the token for real. Pass csrf=False to send a
    form without it (to test that it is refused).

    It reads the site in English (the VI / EN cookie), so messages can be
    checked in one language; tests/test_language.py covers Vietnamese.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_cookie("ui_lang", "en")

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
    try:
        yield app
    finally:
        from app import db

        with app.app_context():
            db.session.remove()
            db.engine.dispose()


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
