"""Bring an existing SQLite database up to date when the app starts.

db.create_all() makes missing *tables*, but never adds new *columns* to a
table that already exists. The live site's SQLite file is older than some
columns, so they are added here. Every step only adds things, checks first,
and is safe to run again. It never deletes data.

SQL Server doesn't use this: run the numbered scripts in database/ instead.
"""

from sqlalchemy import inspect, text

# (table, column, statement). The statements are fixed text written here,
# never built from user input.
NEW_COLUMNS = [
    ("users", "username", "ALTER TABLE users ADD COLUMN username VARCHAR(30)"),
    ("users", "email_verified_at", "ALTER TABLE users ADD COLUMN email_verified_at DATETIME"),
    # 03_reminders.sql
    ("users", "timezone", "ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"),
    ("users", "reminders_enabled", "ALTER TABLE users ADD COLUMN reminders_enabled BOOLEAN NOT NULL DEFAULT 1"),
    ("users", "reminder_hour", "ALTER TABLE users ADD COLUMN reminder_hour INTEGER NOT NULL DEFAULT 9"),
    ("users", "reminder_channels", "ALTER TABLE users ADD COLUMN reminder_channels VARCHAR(60) NOT NULL DEFAULT 'email'"),
    ("subscriptions", "billing_day", "ALTER TABLE subscriptions ADD COLUMN billing_day INTEGER"),
    ("subscriptions", "lead_days", "ALTER TABLE subscriptions ADD COLUMN lead_days VARCHAR(40) NOT NULL DEFAULT '7'"),
    ("subscriptions", "manage_url", "ALTER TABLE subscriptions ADD COLUMN manage_url VARCHAR(2048) NOT NULL DEFAULT ''"),
    # 04_links.sql
    ("links", "url_hash", "ALTER TABLE links ADD COLUMN url_hash VARCHAR(64)"),
    ("links", "favicon_url", "ALTER TABLE links ADD COLUMN favicon_url VARCHAR(2048) NOT NULL DEFAULT ''"),
    # 05_reminder_payload.sql
    ("reminders", "payload_json", "ALTER TABLE reminders ADD COLUMN payload_json TEXT"),
]

AFTER_COLUMNS = [
    # Accounts made before usernames existed get "user_<id>"; same rule as
    # database/02_accounts.sql. They can be renamed later.
    "UPDATE users SET username = 'user_' || id WHERE username IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username)",
    # 03_reminders.sql: older subscriptions keep their single "remind days".
    "UPDATE subscriptions SET lead_days = CAST(remind_days AS TEXT) WHERE lead_days = '7' AND remind_days <> 7",
    "UPDATE subscriptions SET billing_day = CAST(strftime('%d', next_renewal_at) AS INTEGER) WHERE billing_day IS NULL",
    # 04_links.sql (the fingerprints themselves are filled in by Python: links.fill_missing_fingerprints)
    "CREATE INDEX IF NOT EXISTS ix_links_url_hash ON links (url_hash)",
]


def upgrade_sqlite(engine) -> list[str]:
    """Add any missing columns. Returns the names it added (for messages/tests)."""
    added = []
    with engine.begin() as conn:
        tables = set(inspect(conn).get_table_names())
        for table, column, statement in NEW_COLUMNS:
            if table not in tables:
                continue
            existing = {col["name"] for col in inspect(conn).get_columns(table)}
            if column not in existing:
                conn.execute(text(statement))
                added.append(f"{table}.{column}")
        for statement in AFTER_COLUMNS:
            conn.execute(text(statement))
        for table, statement in {
            "bills": "CREATE INDEX IF NOT EXISTS IX_bills_user_date ON bills (user_id, status, transaction_date)",
            "bill_lines": "CREATE INDEX IF NOT EXISTS IX_bill_lines_bill ON bill_lines (bill_id, position)",
        }.items():
            if table in tables:
                conn.execute(text(statement))
    return added
