"""Old SQLite files (like the live site's) get the new columns without losing data."""

import sqlite3

from app import create_app
from app.models import User

OLD_USERS_TABLE = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    last_login_at DATETIME
)
"""


def test_old_sqlite_file_is_upgraded(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(OLD_USERS_TABLE)
        conn.execute(
            "INSERT INTO users VALUES (1, 'owner@example.com', 'hash', 1, '2026-10-14 10:00:00', NULL)"
        )
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")

    app = create_app()
    create_app()  # starting a second time must also work (safe to re-run)

    with app.app_context():
        owner = User.query.one()
        assert owner.username == "user_1"
        assert owner.email == "owner@example.com"
        assert owner.is_admin  # existing admins keep their rights
        assert not owner.email_verified
    with sqlite3.connect(path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "auth_tokens" in tables
    assert "uq_users_username" in indexes
