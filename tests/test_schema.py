"""Readiness must reject a core-only schema even when connection succeeds."""

import pytest

from app import db
from app import schema


def test_current_sqlite_schema_is_ready(app):
    with app.app_context():
        assert schema.schema_issues(db.engine) == []
    result = app.test_cli_runner().invoke(args=["check-db"])
    assert result.exit_code == 0
    assert "bill columns and indexes" in result.output


@pytest.mark.parametrize("defect", ["tables", "column", "index", "unique"])
def test_incomplete_schema_fails_readiness(app, monkeypatch, defect):
    with app.app_context():
        real = schema.inspect(db.engine)

    class Incomplete:
        def get_table_names(self):
            names = real.get_table_names()
            return [n for n in names if n not in {"documents", "bills", "bill_lines"}] if defect == "tables" else names

        def get_columns(self, table):
            return [c for c in real.get_columns(table) if not (defect == "column" and table == "bills" and c["name"] == "document_id")]

        def get_indexes(self, table):
            return [] if defect == "index" and table == "bill_lines" else real.get_indexes(table)

        def get_unique_constraints(self, table):
            return [] if defect == "unique" and table == "documents" else real.get_unique_constraints(table)

    monkeypatch.setattr(schema, "inspect", lambda engine: Incomplete())
    result = app.test_cli_runner().invoke(args=["check-db"])
    assert result.exit_code == 1
    assert "schema is incomplete" in result.output
    expected = {"tables": "missing table: bills", "column": "bills.document_id",
                "index": "bill_lines(bill_id, position)", "unique": "documents(user_id, sha256)"}
    assert expected[defect] in result.output


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
