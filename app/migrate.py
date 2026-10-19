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
]

AFTER_COLUMNS = [
    # Accounts made before usernames existed get "user_<id>"; same rule as
    # database/02_accounts.sql. They can be renamed later.
    "UPDATE users SET username = 'user_' || id WHERE username IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username)",
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
