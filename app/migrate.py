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
]

AFTER_COLUMNS = [
    # Accounts made before usernames existed get "user_<id>"; same rule as
    # database/02_accounts.sql. They can be renamed later.
    "UPDATE users SET username = 'user_' || id WHERE username IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username)",
    # 03_reminders.sql: older subscriptions keep their single "remind days".
    "UPDATE subscriptions SET lead_days = CAST(remind_days AS TEXT) WHERE lead_days = '7' AND remind_days <> 7",
    "UPDATE subscriptions SET billing_day = CAST(strftime('%d', next_renewal_at) AS INTEGER) WHERE billing_day IS NULL",
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
    return added
