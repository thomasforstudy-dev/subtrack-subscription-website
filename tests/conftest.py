"""Shared test setup: every test gets a fresh, empty test database."""

import ipaddress
import os
import socket

import pytest

# Apply before test modules import app (which otherwise reads the real .env).
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DB_SERVER"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-session-key-only"
for name in (
    "DB_USER", "DB_PASSWORD", "GEMINI_API_KEY", "GEMINI_MODEL",
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET", "SITE_URL", "MESSENGER_URL", "ZALO_URL",
):
    os.environ.pop(name, None)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # python-dotenv 1.1.1 does not support PYTHON_DOTENV_DISABLED yet.
    # Replace the loader before collection imports app; undo it on session exit.
    patcher = pytest.MonkeyPatch()
    patcher.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    config.add_cleanup(patcher.undo)


@pytest.fixture(autouse=True)
def local_network_only(monkeypatch):
    """Keep real API/email calls out of tests; allow the loopback preview server."""
    real_connect = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            try:
                is_local = ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                is_local = False
            if not is_local:
                raise OSError("Tests must mock external network connections.")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    # Local HTTP tests should not inherit a workstation's proxy settings.
    monkeypatch.setenv("NO_PROXY", "*")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    from app import db

    try:
        yield app
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def sign_up(client, email="a@example.com", password="password123"):
    return client.post(
        "/register", data={"email": email, "password": password, "confirm": password}
    )


@pytest.fixture()
def user(client):
    sign_up(client)
    return client
