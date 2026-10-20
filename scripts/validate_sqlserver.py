"""Validate migrations/CRUD/workers on two NEW synthetic SQL Server databases.

Run from this checkout with Python 3.14. Uses Windows authentication, never the
app's .env. Refuses existing targets and leaves test databases for inspection.
No DROP, TRUNCATE, production connection, email send, or service change.
"""

import json
import io
import os
import re
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus
from unittest.mock import patch

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATABASES = {
    "clean": ("SubTrack_CodexBills_20261019_Clean", "CREATE DATABASE [SubTrack_CodexBills_20261019_Clean]"),
    "legacy": ("SubTrack_CodexBills_20261019_Legacy", "CREATE DATABASE [SubTrack_CodexBills_20261019_Legacy]"),
}


def dsn(database):
    assert database == "master" or database in {value[0] for value in DATABASES.values()}
    return (r"DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\SQLEXPRESS;"
            f"DATABASE={database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=5")


def execute_script(connection, path):
    sql = path.read_text(encoding="utf-8")
    if path.name == "01_schema.sql":
        sql, count = re.subn(r"IF DB_ID\(N'SubTrack'\) IS NULL\s+CREATE DATABASE SubTrack;\s*GO", "", sql)
        assert count == 1, "Schema database header changed; review the test adapter"
    sql = sql.replace("USE SubTrack;", "-- Test connection already selects its synthetic database.")
    executable = re.sub(r"/\*.*?\*/|--[^\n]*", "", sql, flags=re.S)
    assert not re.search(r"\b(USE|DROP|TRUNCATE)\b|CREATE\s+DATABASE", executable, re.I)
    for batch in re.split(r"(?im)^\s*GO\s*$", sql):
        if batch.strip():
            cursor = connection.execute(batch)
            while cursor.nextset():
                pass


def migrate(kind):
    database, create_sql = DATABASES[kind]
    with pyodbc.connect(dsn("master"), autocommit=True) as master:
        existing = master.execute("SELECT DB_ID(?)", database).fetchone()[0] is not None
        if existing:
            assert "--resume" in sys.argv, "Test target already exists; use --resume only for this validation's synthetic targets"
        else:
            master.execute(create_sql)
    connection = pyodbc.connect(dsn(database), autocommit=True)
    assert connection.execute("SELECT DB_NAME()").fetchone()[0] == database
    if existing:
        assert connection.execute("SELECT COUNT(*) FROM dbo.users WHERE email NOT LIKE ?", "%@example.com").fetchone()[0] == 0
    scripts = sorted((ROOT / "database").glob("[0-9][0-9]_*.sql"))
    execute_script(connection, scripts[0])
    if kind == "legacy" and not existing:
        user_id = connection.execute(
            "INSERT INTO dbo.users(email,password_hash,is_admin) OUTPUT INSERTED.id VALUES(?,?,?)",
            "legacy@example.com", "synthetic-hash", True,
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO dbo.subscriptions(user_id,name,next_renewal_at,remind_days) VALUES(?,?,?,?)",
            user_id, "Legacy synthetic plan", date(2028, 1, 31), 3,
        )
        connection.execute("INSERT INTO dbo.links(user_id,url,title) VALUES(?,?,?)", user_id,
                           "https://example.com/legacy", "Legacy synthetic link")
    for _ in range(2):
        for script in scripts:
            execute_script(connection, script)
    assert connection.execute("SELECT COUNT(*) FROM sys.check_constraints WHERE is_disabled=0").fetchone()[0] >= 8
    assert connection.execute("SELECT COUNT(*) FROM sys.indexes WHERE name IN ('IX_reminders_status','IX_links_user_hash','IX_auth_tokens_user')").fetchone()[0] == 3
    assert connection.execute("SELECT COL_LENGTH('dbo.reminders','payload_json')").fetchone()[0] is not None
    if kind == "legacy":
        user_id = connection.execute("SELECT id FROM dbo.users WHERE email=?", "legacy@example.com").fetchone()[0]
        row = connection.execute("SELECT username,is_admin FROM dbo.users WHERE email=?", "legacy@example.com").fetchone()
        assert row[0] == f"user_{user_id}" and row[1]
        row = connection.execute("SELECT lead_days,billing_day FROM dbo.subscriptions WHERE user_id=?", user_id).fetchone()
        assert row[0] == "3" and row[1] == 31
        assert connection.execute("SELECT COUNT(*) FROM dbo.links WHERE user_id=?", user_id).fetchone()[0] == 1
    connection.close()
    return {"database": database, "scripts": [p.name for p in scripts], "rerun_passes": 2, "legacy_preserved": kind == "legacy"}


def application_checks(bills_only=False):
    database = DATABASES["clean"][0]
    database_url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(database))
    os.environ.update(DB_SERVER="", DATABASE_URL=database_url, APP_ENV="development",
                      SECRET_KEY="sql-validation-test-secret-longer-than-thirty-two-characters",
                      MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="", SUBBY_PROVIDER="fake")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import create_app, db, reminders
        from app.models import Link, Reminder, Subscription, User, utcnow
        app = create_app()
    from tests.html_helpers import Page
    from tests.test_reminder_processes import start_workers

    def post(client, path, data=None):
        page = client.get("/login" if path in ("/register", "/login") else "/subscriptions/")
        token = Page(page.get_data(as_text=True)).form_with("csrf_token")["fields"]["csrf_token"]
        return client.post(path, data={**(data or {}), "csrf_token": token})

    me, other = app.test_client(), app.test_client()
    for client, name in ((me, "sql_owner"), (other, "sql_other")):
        with app.app_context():
            exists = User.query.filter_by(username=name).first() is not None
        if exists:
            assert post(client, "/login", {"identifier": name, "password": "SyntheticSQL2026!"}).status_code == 302
        else:
            assert post(client, "/register", {"username": name, "email": f"{name}@example.com",
                        "password": "SyntheticSQL2026!", "confirm": "SyntheticSQL2026!"}).status_code == 302
    if bills_only:
        return bill_checks(app, me, other, post)
    form = {"name": "SQL synthetic plan", "amount": "10.00", "currency": "USD", "cycle": "monthly",
            "next_renewal_at": "2026-11-10", "lead_days": "7", "manage_url": "https://example.com/manage"}
    assert me.post("/subscriptions/new", data=form).status_code == 400  # real CSRF boundary
    with app.app_context():
        has_sub = Subscription.query.count() != 0
    if not has_sub:
        assert post(me, "/subscriptions/new", form).status_code == 302
    with app.app_context():
        sub = Subscription.query.one()
        sub_id = sub.id
        owner = User.query.filter_by(username="sql_owner").one()
        owner.email_verified_at = utcnow()
        owner.timezone = "UTC"
        db.session.commit()
        rollback_user = User(username="rollback_only", email="rollback@example.com")
        rollback_user.set_password("SyntheticSQL2026!")
        db.session.add(rollback_user)
        db.session.flush()
        db.session.rollback()
        assert User.query.filter_by(username="rollback_only").count() == 0
    assert other.get(f"/subscriptions/{sub_id}/edit").status_code == 404
    assert post(other, f"/subscriptions/{sub_id}/archive").status_code == 404
    assert post(me, f"/subscriptions/{sub_id}/archive").status_code == 302
    assert post(me, f"/subscriptions/{sub_id}/restore").status_code == 302
    assert post(me, f"/subscriptions/{sub_id}/edit", {**form, "notes": "SQL transaction test"}).status_code == 302
    with app.app_context():
        has_link = Link.query.count() != 0
    if not has_link:
        assert post(me, "/links/new", {"url": "https://example.com/sql", "title": "Synthetic SQL link"}).status_code == 302
    assert b"Synthetic SQL link" not in other.get("/links/").data
    assert post(me, "/settings", {"timezone": "UTC", "reminder_hour": "9", "reminders_enabled": "on", "channels": "email"}).status_code == 302
    assert me.get("/dashboard.json").get_json()["projected"][0]["monthly"] == "10.00"

    with app.app_context():
        reminders.run(datetime(2026, 11, 3, 9), dry_run=True)
        item_id = Reminder.query.one().id
    bill_results = bill_checks(app, me, other, post)
    provider = ROOT / "instance" / "sql-bills-fake-provider.db"
    assert not provider.exists(), "Fake provider target already exists"
    with sqlite3.connect(provider) as conn:
        conn.execute("CREATE TABLE deliveries (idempotency_key TEXT PRIMARY KEY,payload TEXT NOT NULL)")
    assert sorted(start_workers(database_url, item_id, "2026-11-03T09:00:00", ["normal", "normal"], provider)) == ["lost", "sent"]
    with app.app_context():
        row = Reminder(subscription_id=sub_id, user_id=Subscription.query.one().user_id,
                       renewal_date=date(2026, 11, 10), lead_days=3, next_try_at=datetime(2026, 11, 7, 9))
        db.session.add(row)
        db.session.commit()
        crash_id = row.id
    start_workers(database_url, crash_id, "2026-11-07T09:00:00", ["crash_after_send"], provider, expected_crash=True)
    assert start_workers(database_url, crash_id, "2026-11-08T08:00:00", ["normal"], provider) == ["sent"]
    with sqlite3.connect(provider) as conn:
        assert conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 2
    with app.app_context():
        assert Reminder.query.filter_by(status="sent").count() == 2
        db.session.remove()
        db.engine.dispose()
    return {"crud_csrf_isolation_rollback": "passed", "separate_process_claim": "passed",
            "crash_retry_identical_payload": "passed", "bills": bill_results, "real_emails_sent": 0}


def bill_checks(app, me, other, post):
    from app import db
    from app.models import Bill, BillLine, Document
    from app.schema import schema_issues

    with app.app_context():
        assert schema_issues(db.engine) == []
    assert app.test_cli_runner().invoke(args=["check-db"]).exit_code == 0
    # Generate a real PNG; no private invoice or external request.
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(buffer, format="PNG")
    png = buffer.getvalue()
    assert me.post("/bills/upload", data={"file": (io.BytesIO(png), "synthetic.png")}).status_code == 400
    assert post(me, "/bills/upload", {"file": (io.BytesIO(png), "synthetic.png")}).status_code == 302
    with app.app_context():
        document_id = Document.query.one().id
    form = {"merchant": "Synthetic SQL receipt", "currency": "USD", "total": "9999999999.99",
            "kind": "receipt", "document_id": str(document_id), "item_name_1": "SQL boundary",
            "item_qty_1": "1", "item_price_1": "9999999999.99"}
    assert post(other, "/bills/new", form).status_code == 404
    with app.app_context():
        exists = Bill.query.count() > 0
    if not exists:
        assert post(me, "/bills/new", form).status_code == 302
    with app.app_context():
        bill = Bill.query.one()
        bill_id = bill.id
        assert bill.document_id == document_id and bill.source == "upload"
        assert bill.total == Decimal("9999999999.99")
        assert BillLine.query.one().amount == Decimal("9999999999.99")
        bill.merchant = "Rolled back edit"
        db.session.flush()
        db.session.rollback()
        assert Bill.query.one().merchant == "Synthetic SQL receipt"
    overflow = {**form, "merchant": "Must not save", "item_qty_1": "9999999", "item_price_1": "99999999.99"}
    response = post(me, f"/bills/{bill_id}/edit", overflow)
    assert response.status_code == 200 and b"too big" in response.data
    with app.app_context():
        assert Bill.query.one().merchant == "Synthetic SQL receipt"
        assert BillLine.query.one().amount == Decimal("9999999999.99")
    assert post(me, f"/bills/{bill_id}/edit", {"notes": "Synthetic SQL edit verified"}).status_code == 302
    with app.app_context():
        assert Bill.query.one().notes == "Synthetic SQL edit verified"
    for path in (f"/bills/{bill_id}/edit", f"/bills/files/{document_id}", f"/bills/new?document_id={document_id}"):
        assert other.get(path).status_code == 404
    for action in ("paid", "archive", "restore"):
        assert post(other, f"/bills/{bill_id}/{action}").status_code == 404
        assert me.post(f"/bills/{bill_id}/{action}").status_code == 400
        assert post(me, f"/bills/{bill_id}/{action}").status_code == 302
    for format in ("json", "csv", "md"):
        assert me.get(f"/bills/export.{format}").status_code == 200
        assert b"Synthetic SQL receipt" not in other.get(f"/bills/export.{format}").data
    assert me.get(f"/bills/files/{document_id}").data == png
    return {"schema_readiness": "passed", "crud_rollback_ownership_csrf": "passed",
            "decimal_boundary_and_rejected_product": "passed", "private_file_association_and_exports": "passed"}


def main():
    if "--bills-only" in sys.argv:
        result = application_checks(bills_only=True)
        (ROOT / "instance" / "sql-bills-recheck.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return
    if "--calendar-only" in sys.argv:
        result = calendar_checks()
        (ROOT / "instance" / "sql-calendar-validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return
    result = {"migrations": [migrate("clean"), migrate("legacy")], "application": application_checks()}
    target = ROOT / "instance" / "sqlserver-validation.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def calendar_checks():
    """Read the synthetic account created by the completed SQL integration run."""
    database_url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(DATABASES["clean"][0]))
    os.environ.update(DB_SERVER="", DATABASE_URL=database_url, APP_ENV="development",
                      SECRET_KEY="sql-calendar-test-secret-longer-than-thirty-two-characters",
                      MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="", SUBBY_PROVIDER="fake")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import create_app, db
        from app.models import Subscription, User
        app = create_app()
    from tests.html_helpers import Page

    client = app.test_client()
    fields = Page(client.get("/login").get_data(as_text=True)).form_with("csrf_token")["fields"]
    assert client.post("/login", data={"identifier": "sql_owner", "password": "SyntheticSQL2026!",
                                     "csrf_token": fields["csrf_token"]}).status_code == 302
    with app.app_context():
        owner = User.query.filter_by(username="sql_owner").one()
        item_id = Subscription.query.filter_by(user_id=owner.id).one().id
    assert client.get("/calendar/").status_code == 200
    assert client.get(f"/calendar/subscriptions/{item_id}").status_code == 200
    response = client.get("/calendar/renewals.ics")
    assert response.status_code == 200 and response.mimetype == "text/calendar"
    assert response.data.count(b"BEGIN:VEVENT\r\n") == 1
    assert "no-store" in response.headers["Cache-Control"]
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    return {"database": DATABASES["clean"][0], "calendar_index_review_and_ics": "passed", "events": 1}


if __name__ == "__main__":
    main()
