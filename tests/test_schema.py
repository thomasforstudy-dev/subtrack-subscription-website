"""Readiness must reject a core-only schema even when connection succeeds."""

import pytest

from app import db
from app import schema


def test_current_sqlite_schema_is_ready(app):
    with app.app_context():
        assert schema.schema_issues(db.engine) == []
    result = app.test_cli_runner().invoke(args=["check-db"])
    assert result.exit_code == 0
    assert "columns and indexes exist" in result.output


@pytest.mark.parametrize("defect", ["tables", "column", "index", "unique", "slot", "code_column"])
def test_incomplete_schema_fails_readiness(app, monkeypatch, defect):
    with app.app_context():
        real = schema.inspect(db.engine)

    class Incomplete:
        def get_table_names(self):
            names = real.get_table_names()
            return [n for n in names if n not in {"documents", "bills", "bill_lines"}] if defect == "tables" else names

        def get_columns(self, table):
            drop = {"column": ("bills", "document_id"), "code_column": ("email_codes", "code_hash")}.get(defect)
            return [c for c in real.get_columns(table) if (table, c["name"]) != drop]

        def get_indexes(self, table):
            if (defect, table) in {("index", "bill_lines"), ("slot", "api_tokens")}:
                return []
            return real.get_indexes(table)

        def get_unique_constraints(self, table):
            return [] if defect == "unique" and table == "documents" else real.get_unique_constraints(table)

    monkeypatch.setattr(schema, "inspect", lambda engine: Incomplete())
    result = app.test_cli_runner().invoke(args=["check-db"])
    assert result.exit_code == 1
    assert "schema is incomplete" in result.output
    expected = {"tables": "missing table: bills", "column": "bills.document_id",
                "index": "bill_lines(bill_id, position)", "unique": "documents(user_id, sha256)",
                # the index that enforces the 5-token limit, and a column of a new table
                "slot": "missing unique index: api_tokens(user_id, slot)",
                "code_column": "missing column: email_codes.code_hash"}
    assert expected[defect] in result.output


def test_retired_table_columns_are_not_required(app, monkeypatch):
    # reminder_logs is kept but unused; an old file without its newer column is fine.
    with app.app_context():
        real = schema.inspect(db.engine)

    class OldLogs:
        get_table_names = real.get_table_names
        get_indexes = real.get_indexes
        get_unique_constraints = real.get_unique_constraints

        def get_columns(self, table):
            return [c for c in real.get_columns(table) if (table, c["name"]) != ("reminder_logs", "renewal_date")]

    monkeypatch.setattr(schema, "inspect", lambda engine: OldLogs())
    assert app.test_cli_runner().invoke(args=["check-db"]).exit_code == 0


def test_sqlserver_unique_indexes_work_without_unique_reflection(app, monkeypatch):
    with app.app_context():
        real = schema.inspect(db.engine)

    class SqlServerLike:
        get_table_names = real.get_table_names
        get_columns = real.get_columns

        def get_indexes(self, table):
            return real.get_indexes(table) + [dict(item, unique=True) for item in real.get_unique_constraints(table)]

        def get_unique_constraints(self, table):
            raise NotImplementedError

    monkeypatch.setattr(schema, "inspect", lambda engine: SqlServerLike())
    assert app.test_cli_runner().invoke(args=["check-db"]).exit_code == 0
