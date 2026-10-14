"""Shared test setup: every test gets a fresh, empty test database."""

import os

import pytest

# Never touch SQL Server or your real .env data while testing.
os.environ["DB_SERVER"] = ""


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def sign_up(client, email="a@example.com", password="password123"):
    return client.post("/register", data={"email": email, "password": password})


@pytest.fixture()
def user(client):
    sign_up(client)
    return client
