"""Old SQLite files (like the live site's) get the new columns without losing data."""

import sqlite3

from app import create_app
from app.links import url_fingerprint
from app.models import Link, Subscription, User

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


OLD_SUBSCRIPTIONS_TABLE = """
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    cycle VARCHAR(20) NOT NULL,
    next_renewal_at DATE NOT NULL,
    remind_days INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    notes TEXT NOT NULL,
    created_at DATETIME NOT NULL
)
"""


OLD_LINKS_TABLE = """
CREATE TABLE links (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    url VARCHAR(2048) NOT NULL,
    title VARCHAR(200) NOT NULL,
    tags VARCHAR(200) NOT NULL,
    notes TEXT NOT NULL,
    is_pinned BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL
)
"""


def test_old_sqlite_file_is_upgraded(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(OLD_USERS_TABLE)
        conn.execute(OLD_SUBSCRIPTIONS_TABLE)
        conn.execute(OLD_LINKS_TABLE)
        conn.execute(
            "INSERT INTO links VALUES (1, 1, 'https://example.com/a', 'A', '', '', 0, '2026-10-14 10:00:00')"
        )
        conn.execute(
            "INSERT INTO users VALUES (1, 'owner@example.com', 'hash', 1, '2026-10-14 10:00:00', NULL)"
        )
        conn.execute(
            "INSERT INTO subscriptions VALUES (1, 1, 'Netflix', 9.99, 'USD', 'monthly', '2026-10-31', 3, "
            "'active', '', '2026-10-14 10:00:00')"
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
        assert owner.timezone == "UTC" and owner.reminders_enabled and owner.channel_list == ["email"]
        sub = Subscription.query.one()
        assert sub.lead_days == "3"  # kept its old "remind 3 days before"
        assert sub.billing_day == 31
        assert sub.manage_url == ""
        link = Link.query.one()
        assert link.url_hash == url_fingerprint("https://example.com/a")
        assert link.favicon_url == "https://example.com/favicon.ico"
    with sqlite3.connect(path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"auth_tokens", "renewals", "reminders"} <= tables
    assert "uq_users_username" in indexes
