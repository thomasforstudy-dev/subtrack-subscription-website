"""Dedicated synthetic SQL Server preview. Never reads .env or uses SQLite."""

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus
from unittest.mock import patch

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INSTANCE = ROOT / "instance"
ACCESS = INSTANCE / "sql-preview-access.json"
DATABASE = "SubTrack_CodexMainPreview_20261020"
RESTORE_DATABASE = "SubTrack_CodexMainRestore_20261020"
PORT = 8774
SESSION_COOKIE_NAME = "subtrack_sql_main_preview_session"
REMEMBER_COOKIE_NAME = "subtrack_sql_main_preview_remember"


def dsn(database=DATABASE):
    if database not in {"master", DATABASE, RESTORE_DATABASE}:
        raise ValueError("Database is not an allowlisted synthetic target")
    return (r"DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost\SQLEXPRESS;"
            f"DATABASE={database};Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
            "Connection Timeout=5;APP=SubTrackCodexSQLPreview")


def restrict_file(path):
    """Owner only; never print generated passwords or the session signing key."""
    if os.name == "nt":
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True)
        sid = next(csv.reader(io.StringIO(result.stdout.strip())))[1]
        subprocess.run(["icacls", str(path), "/grant:r", "*" + sid + ":(F)"],
                       check=True, capture_output=True)
        subprocess.run(["icacls", str(path), "/inheritance:r"],
                       check=True, capture_output=True)
    else:
        path.chmod(0o600)


def access_details(create=False):
    INSTANCE.mkdir(exist_ok=True)
    if not ACCESS.exists() or (create and ACCESS.stat().st_size == 0):
        if not create:
            raise RuntimeError("Initialize the dedicated SQL preview first")
        details = {"database": DATABASE, "port": PORT, "instance_id": secrets.token_hex(12),
                   "secret": secrets.token_hex(32), "accounts": [
                       {"username": name, "email": name + "@example.com", "password": secrets.token_urlsafe(18) + "Aa1!"}
                       for name in ["sql_review_a", "sql_review_b", *[f"sql_load_{n:02d}" for n in range(10)]] ]}
        ACCESS.touch(exist_ok=True)
        restrict_file(ACCESS)
        ACCESS.write_text(json.dumps(details, indent=2), encoding="utf-8")
    restrict_file(ACCESS)
    details = json.loads(ACCESS.read_text(encoding="utf-8"))
    if details["database"] != DATABASE or details["port"] != PORT:
        raise RuntimeError("Local access file belongs to a different preview")
    return details


def apply_migrations():
    from scripts.validate_sqlserver import execute_script

    with pyodbc.connect(dsn(), autocommit=True) as connection:
        if connection.execute("SELECT DB_NAME()").fetchone()[0] != DATABASE:
            raise RuntimeError("Unexpected database; refusing migrations")
        scripts = sorted((ROOT / "database").glob("[0-9][0-9]_*.sql"))
        for script in scripts:
            execute_script(connection, script)
    return [script.name for script in scripts]


def build_app(database=DATABASE, uploads=None):
    if database not in {DATABASE, RESTORE_DATABASE}:
        raise ValueError("Only synthetic databases may run this preview")
    details = access_details()
    # Explicit values override inherited owner settings. Dotenv is patched BEFORE app import.
    os.environ.update(DB_SERVER="", DATABASE_URL="mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(database)),
                      APP_ENV="development", SECRET_KEY=details["secret"], MAIL_BACKEND="memory",
                      SUBBY_PROVIDER="fake", SUBBY_FALLBACK="", RESEND_API_KEY="", GEMINI_API_KEY="",
                      GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="", GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET="",
                      MESSENGER_URL="", ZALO_URL="", SITE_URL=f"http://127.0.0.1:{PORT}")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import create_app, db
        app = create_app()
    app.config.update(SESSION_COOKIE_NAME=SESSION_COOKIE_NAME,
                      REMEMBER_COOKIE_NAME=REMEMBER_COOKIE_NAME)
    from sqlalchemy import event, text
    from app.schema import schema_issues
    from app import links

    # Public link metadata fetching is intentionally unavailable in this fixture.
    links.fetch_preview = lambda url: {}
    app.cli.commands.pop("send-reminders", None)
    app.cli.commands.pop("process-documents", None)
    os.environ.update(OCR_PROVIDER="", OCR_API_KEY="", OCR_BASE_URL="")
    if uploads is not None:
        app.instance_path = str(Path(uploads).parent)
    with app.app_context():
        if db.engine.dialect.name != "mssql":
            raise RuntimeError("SQL Server required; SQLite fallback is forbidden")

        @event.listens_for(db.engine, "connect")
        def statement_timeout(connection, record):
            connection.timeout = 8

        with db.engine.connect() as connection:
            actual = connection.execute(text("SELECT DB_NAME()")).scalar_one()
        if actual != database:
            raise RuntimeError("Unexpected database identity")
        if schema_issues(db.engine):
            raise RuntimeError("Synthetic SQL schema is incomplete; initialize it first")
    return app


def snapshots(app):
    from app import db
    from sqlalchemy import select

    with app.app_context():
        result = {}
        for table in db.metadata.sorted_tables:
            rows = db.session.execute(select(table).order_by(*table.primary_key.columns)).all()
            result[table.name] = {"rows": len(rows), "digest": hashlib.sha256(repr(rows).encode()).hexdigest()}
        return result


def initialize():
    access_details(create=True)
    with pyodbc.connect(dsn("master"), autocommit=True) as master:
        if master.execute("SELECT DB_ID(?)", DATABASE).fetchone()[0] is None:
            master.execute("CREATE DATABASE [SubTrack_CodexMainPreview_20261020]")
    scripts = apply_migrations()
    app = build_app()
    from app import db
    from app.models import Bill, BillLine, Link, Subscription, User, utcnow
    from app.links import url_fingerprint

    with app.app_context():
        for account in access_details()["accounts"]:
            user = User.query.filter_by(username=account["username"]).first()
            if user is not None:
                continue  # no reset or deletion on repeated initialization
            user = User(username=account["username"], email=account["email"], timezone="Asia/Ho_Chi_Minh",
                        email_verified_at=utcnow(), reminders_enabled=False)
            user.set_password(account["password"])
            db.session.add(user)
            db.session.flush()
            count = 25 if user.username.startswith("sql_review") else 3
            for number in range(count):
                renewal = date.today() + timedelta(days=number + 1)
                db.session.add(Subscription(user_id=user.id, name=f"{user.username} synthetic plan {number:02d}",
                    amount=Decimal("10.01"), currency="USD", cycle="monthly", next_renewal_at=renewal,
                    billing_day=renewal.day, lead_days="14,7,3", remind_days=14))
                bill = Bill(user_id=user.id, merchant=f"{user.username} synthetic shop {number:02d}",
                            currency="USD", total=Decimal("3.25"), transaction_date=date.today(), category="food")
                bill.lines = [BillLine(position=1, description="Synthetic item", quantity=Decimal("1"),
                                       unit_price=Decimal("3.25"), amount=Decimal("3.25"))]
                db.session.add(bill)
            url = "https://example.invalid/" + user.username
            db.session.add(Link(user_id=user.id, url=url, title=user.username + " synthetic link",
                                url_hash=url_fingerprint(url), favicon_url=""))
        db.session.commit()
    before = snapshots(app)
    for _ in range(2):
        apply_migrations()
        if snapshots(app) != before:
            raise RuntimeError("Migration rerun changed existing synthetic records")
    report = {"database": DATABASE, "provider": "mssql", "authentication": "Windows integrated",
              "scripts": scripts, "initial_application_plus_reruns": 3, "reruns": 2,
              "existing_records_unchanged": True, "tables": before}
    (INSTANCE / "sql-preview-migrations.json").write_text(json.dumps(report, indent=2))
    print("Synthetic SQL preview initialized; migrations rerun twice, existing records preserved.")


def serve_preview():
    details = access_details()
    app = build_app()
    from app import db
    from flask import jsonify
    from sqlalchemy import text
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip())
    label = revision[:12] + (" + local changes" if dirty else "")

    @app.get("/__sql_preview__/health")
    def health():
        with db.engine.connect() as connection:
            actual = connection.execute(text("SELECT DB_NAME()")).scalar_one()
        if actual != DATABASE:
            return jsonify(error="Database identity mismatch"), 503
        return jsonify(provider="mssql", database=actual, revision=revision, dirty=dirty,
                       instance_id=details["instance_id"], pid=os.getpid(), mail="memory", ai="fake")

    @app.after_request
    def preview_boundary(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'")
        if response.mimetype == "text/html":
            banner = ('<aside role="status" style="padding:12px;background:#fff0bf;color:#342500;text-align:center">'
                      '<strong>SQL Server development preview — synthetic data only</strong><br>'
                      f'Database: {html.escape(DATABASE)} · Provider: mssql · Revision: {html.escape(label)}<br>'
                      'Windows authentication · Mail: memory · AI: fake · Schedulers/external writes: disabled</aside>'
                      '<script>document.addEventListener("click",function(e){const a=e.target.closest("a[href]");'
                      'if(a&&new URL(a.href,location.href).origin!==location.origin){e.preventDefault();'
                      'alert("External links are disabled in this synthetic SQL preview.");}});</script>')
            response.set_data(re.sub(r"(<body\b[^>]*>)", lambda match: match[1] + banner,
                                     response.get_data(as_text=True), count=1))
        return response

    real_connect = socket.socket.connect

    def loopback_only(sock, address):
        import ipaddress
        if sock.family in (socket.AF_INET, socket.AF_INET6) and not ipaddress.ip_address(address[0]).is_loopback:
            raise OSError("External network disabled in SQL preview")
        return real_connect(sock, address)

    socket.socket.connect = loopback_only
    from waitress import serve
    print(f"SQL preview http://127.0.0.1:{PORT}; database {DATABASE}; revision {label}", flush=True)
    serve(app, host="127.0.0.1", port=PORT, threads=8, channel_timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "serve"])
    args = parser.parse_args()
    try:
        initialize() if args.action == "init" else serve_preview()
    except Exception as error:
        print(f"SQL preview failed ({type(error).__name__}); no SQLite fallback. See setup/SQL service status.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
