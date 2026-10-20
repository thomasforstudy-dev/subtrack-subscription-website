"""Read-only schema readiness, including the private bill/file association."""

from sqlalchemy import inspect


EXPECTED_TABLES = {
    "users", "subscriptions", "reminder_logs", "links", "auth_tokens", "renewals", "reminders",
    "documents", "bills", "bill_lines",
}


def schema_issues(engine):
    from app.models import Bill, BillLine, Document

    inspector = inspect(engine)
    found = set(inspector.get_table_names())
    problems = [f"missing table: {name}" for name in sorted(EXPECTED_TABLES - found)]
    for model in (Document, Bill, BillLine):
        table = model.__tablename__
        if table not in found:
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        for name in sorted(set(model.__table__.columns.keys()) - columns):
            problems.append(f"missing column: {table}.{name}")
        # Names differ between SQLAlchemy's SQLite schema and numbered T-SQL.
        indexes = inspector.get_indexes(table)
        # SQLAlchemy's SQL Server dialect exposes unique constraints as indexes;
        # get_unique_constraints itself raises NotImplementedError there.
        try:
            uniques = inspector.get_unique_constraints(table)
        except NotImplementedError:
            uniques = []
        indexes += uniques
        indexed = {tuple(item["column_names"]) for item in indexes}
        required = {
            "documents": [("stored_name",), ("user_id", "sha256")],
            "bills": [("user_id", "status", "transaction_date")],
            "bill_lines": [("bill_id", "position")],
        }
        for names in required[table]:
            exists = names in indexed
            if table == "documents":
                unique_columns = {tuple(item["column_names"]) for item in uniques}
                unique_columns.update(tuple(item["column_names"]) for item in indexes if item.get("unique"))
                exists = names in unique_columns
            if not exists:
                problems.append(f"missing index: {table}({', '.join(names)})")
    return problems
