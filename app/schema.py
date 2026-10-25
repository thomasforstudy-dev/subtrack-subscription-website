"""Read-only schema readiness: tables, every model column, and the indexes
that the app's safety rules depend on."""

from sqlalchemy import inspect


EXPECTED_TABLES = {
    "users", "subscriptions", "reminder_logs", "links", "auth_tokens", "renewals", "reminders",
    "documents", "bills", "bill_lines",
    # 07_bill_jobs.sql: reading uploaded bills
    "document_jobs", "document_pages", "bill_drafts", "bill_draft_revisions",
    # 08_api_tokens.sql: tokens for the Chrome extension
    "api_tokens",
    # 09_email_codes.sql: 6-digit codes in the confirm email
    "email_codes",
    # 10_cards.sql: the card holder on the Bills page
    "cards",
}

# Kept (never deleted) but no longer read or written by the app, so their
# columns don't matter: reminder_logs was replaced by reminders.
RETIRED_TABLES = {"reminder_logs"}

# (columns, must it be unique?). Index names differ between SQLAlchemy's SQLite
# schema and the numbered T-SQL scripts, so they are matched by their columns.
REQUIRED_INDEXES = {
    "documents": [(("stored_name",), True), (("user_id", "sha256"), True)],  # private file names, no duplicates
    "bills": [(("user_id", "status", "transaction_date"), False)],
    "bill_lines": [(("bill_id", "position"), False)],
    "document_jobs": [(("document_id",), True)],  # one reading job per file
    "api_tokens": [(("token_hash",), True), (("user_id", "slot"), True)],  # the 5-token limit
    "email_codes": [(("user_id", "used_at"), False)],
    "cards": [(("user_id", "removed_at"), False)],
}


def schema_issues(engine):
    from app import db

    inspector = inspect(engine)
    found = set(inspector.get_table_names())
    problems = [f"missing table: {name}" for name in sorted(EXPECTED_TABLES - found)]

    # Every column the app's models use must exist (old databases miss new ones).
    for table in db.metadata.sorted_tables:
        if table.name not in EXPECTED_TABLES or table.name not in found or table.name in RETIRED_TABLES:
            continue
        columns = {column["name"] for column in inspector.get_columns(table.name)}
        for name in sorted(set(table.columns.keys()) - columns):
            problems.append(f"missing column: {table.name}.{name}")

    for table, needed in REQUIRED_INDEXES.items():
        if table not in found:
            continue
        indexes = inspector.get_indexes(table)
        # SQLAlchemy's SQL Server dialect exposes unique constraints as indexes;
        # get_unique_constraints itself raises NotImplementedError there.
        try:
            uniques = inspector.get_unique_constraints(table)
        except NotImplementedError:
            uniques = []
        any_index = {tuple(item["column_names"]) for item in indexes + uniques}
        unique_index = {tuple(item["column_names"]) for item in uniques}
        unique_index.update(tuple(item["column_names"]) for item in indexes if item.get("unique"))
        for names, unique in needed:
            if names not in (unique_index if unique else any_index):
                kind = "unique index" if unique else "index"
                problems.append(f"missing {kind}: {table}({', '.join(names)})")
    return problems
