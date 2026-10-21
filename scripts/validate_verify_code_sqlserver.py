"""Check migration 09 (email_codes: 6-digit codes) on the synthetic SQL Server test database.

Run from the repo folder:  .venv\\Scripts\\python scripts\\validate_verify_code_sqlserver.py
Only the allowlisted synthetic database (scripts/validate_sqlserver.py), Windows
login, never the app's .env. Adds one synthetic @example.com account. No email.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from unittest.mock import patch

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_sqlserver import DATABASES, dsn, execute_script  # noqa: E402

DATABASE = DATABASES["clean"][0]
RUN = datetime.now().strftime("%Y%m%d%H%M%S")


def migrate() -> dict:
    connection = pyodbc.connect(dsn(DATABASE), autocommit=True)
    assert connection.execute("SELECT DB_NAME()").fetchone()[0] == DATABASE
    scripts = sorted((ROOT / "database").glob("[0-9][0-9]_*.sql"))
    for _ in range(2):  # every script must be safe to run twice
        for script in scripts:
            execute_script(connection, script)
    assert connection.execute("SELECT OBJECT_ID(N'dbo.email_codes', N'U')").fetchone()[0] is not None
    assert connection.execute("SELECT 1 FROM sys.indexes WHERE name = N'IX_email_codes_user'").fetchone()
    connection.close()
    return {"database": DATABASE, "scripts": [s.name for s in scripts], "passes": 2, "email_codes_table": True}


def application_checks() -> dict:
    with patch("dotenv.load_dotenv", return_value=False):
        from tests.conftest import CSRFClient, sign_up  # sets SQLite first; overridden below
        from app import create_app, db, mailer
        from app.models import User
        os.environ.update(DB_SERVER="", DATABASE_URL="mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(DATABASE)),
                          APP_ENV="development", SECRET_KEY="sql-verify-code-test-secret-longer-than-32-chars",
                          MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="", SUBBY_PROVIDER="fake")
        app = create_app()
    app.config.update(TESTING=True)
    app.test_client_class = CSRFClient
    with app.app_context():
        assert db.engine.dialect.name == "mssql"
    client = app.test_client()
    email = f"code-{RUN}@example.com"
    sign_up(client, email, username=f"code_{RUN}")
    code = re.search(r"code is: (\d{6})", mailer.sent[-1].text).group(1)
    client.post("/verify-email/code", data={"code": code})
    with app.app_context():
        confirmed = User.query.filter_by(email=email).one().email_verified
        db.session.remove()
        db.engine.dispose()
    assert confirmed
    return {"code_saved_and_confirmed": True}


if __name__ == "__main__":
    report = {"run": RUN, "migrations": migrate(), "application": application_checks()}
    out = ROOT / "instance" / "sql-verify-code.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
