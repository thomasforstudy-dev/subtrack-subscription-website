"""Check migration 08 and extension API tokens on the synthetic SQL Server test database.

Run from the repo folder:  .venv\\Scripts\\python scripts\\validate_api_tokens_sqlserver.py
Uses Codex's allowlisted helpers (scripts/validate_sqlserver.py): only the
synthetic database SubTrack_CodexBills_20261019_Clean, Windows login, never the
app's .env and never the real SubTrack database. Adds only synthetic rows
(@example.com) and leaves them for inspection. No DROP/TRUNCATE, no email.
"""

import json
import os
import re
import sys
import threading
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus
from unittest.mock import patch

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_sqlserver import DATABASES, dsn, execute_script  # noqa: E402

DATABASE = DATABASES["clean"][0]
RUN = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")
SECRET = re.compile(r'value="(st_[A-Za-z0-9_-]{43})"')


def migrate() -> dict:
    connection = pyodbc.connect(dsn(DATABASE), autocommit=True)
    assert connection.execute("SELECT DB_NAME()").fetchone()[0] == DATABASE
    scripts = sorted((ROOT / "database").glob("[0-9][0-9]_*.sql"))
    for _ in range(2):  # every script must be safe to run twice
        for script in scripts:
            execute_script(connection, script)
    assert connection.execute("SELECT OBJECT_ID(N'dbo.api_tokens', N'U')").fetchone()[0] is not None
    unique = connection.execute(
        "SELECT name FROM sys.key_constraints WHERE type = 'UQ' AND name = N'UQ_api_tokens_hash'").fetchone()
    assert unique is not None
    index = connection.execute(
        "SELECT is_unique, has_filter, filter_definition FROM sys.indexes WHERE name = N'UX_api_tokens_user_slot'"
    ).fetchone()
    assert index is not None and index[0] and index[1], index
    connection.close()
    return {"database": DATABASE, "scripts": [s.name for s in scripts], "passes": 2,
            "slot_index_filter": index[2]}


def application_checks() -> dict:
    with patch("dotenv.load_dotenv", return_value=False):
        # Import the test helpers FIRST: tests/conftest.py sets DATABASE_URL to an
        # in-memory SQLite database when it is imported.
        from tests.conftest import CSRFClient, sign_up
        from app import api_tokens, create_app, db, tokens
        from app.models import ApiToken, User, utcnow
        from app.schedule import local_now
        from app.schema import schema_issues
        from sqlalchemy.exc import IntegrityError
        os.environ.update(DB_SERVER="", DATABASE_URL="mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(DATABASE)),
                          APP_ENV="development", SECRET_KEY="sql-api-tokens-test-secret-longer-than-32-chars",
                          MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="", SUBBY_PROVIDER="fake")
        app = create_app()
    app.config.update(TESTING=True)
    app.test_client_class = CSRFClient
    results = {}
    with app.app_context():
        assert db.engine.dialect.name == "mssql", db.engine.dialect.name
        results["database"] = db.session.execute(db.text("SELECT DB_NAME()")).scalar()
        assert results["database"] == DATABASE
        results["schema_issues"] = schema_issues(db.engine)
        assert results["schema_issues"] == [], results["schema_issues"]

    def make_token(client, name):
        page = client.post("/settings/tokens", data={"name": name, "days": "90", "scopes": "renewals:read"})
        found = SECRET.search(page.get_data(as_text=True))
        return page.status_code, (found.group(1) if found else None)

    def api(path, secret):
        return app.test_client().get(path, headers={"Authorization": f"Bearer {secret}"})

    owner = app.test_client()
    sign_up(owner, f"tokens-owner-{RUN}@example.com", username=f"tok_owner_{RUN}")
    other = app.test_client()
    sign_up(other, f"tokens-other-{RUN}@example.com", username=f"tok_other_{RUN}")
    today = local_now("UTC").date()
    for client, name, days in ((owner, f"Owner plan {RUN}", 2), (other, f"Other plan {RUN}", 1)):
        client.post("/subscriptions/new", data={"name": name, "amount": "260000", "currency": "VND", "cycle": "monthly",
                                                "next_renewal_at": (today + timedelta(days=days)).isoformat(),
                                                "lead_days": "3"})

    # Five through the website, the sixth refused; only hashes stored.
    made = [make_token(owner, f"Chrome {n}") for n in range(6)]
    assert [code for code, _ in made] == [200] * 5 + [409], made
    secrets_made = [secret for _, secret in made[:5]]
    with app.app_context():
        owner_id = User.query.filter_by(email=f"tokens-owner-{RUN}@example.com").one().id
        rows = ApiToken.query.filter_by(user_id=owner_id).all()
        assert sorted(t.slot for t in rows) == [1, 2, 3, 4, 5]
        assert {t.token_hash for t in rows} == {api_tokens.hash_secret(s) for s in secrets_made}
    results["five_then_409_hash_only"] = True

    # The filtered unique index refuses a second token in a used slot...
    with app.app_context():
        db.session.add(ApiToken(user_id=owner_id, name="dup", token_hash=f"{RUN:0<64}", prefix="st_dup",
                                scopes="renewals:read", slot=1, expires_at=utcnow() + timedelta(days=1)))
        try:
            db.session.commit()
            raise AssertionError("two active tokens in slot 1 were accepted")
        except IntegrityError:
            db.session.rollback()
    results["slot_index_refuses_duplicate"] = True

    # The API: the owner's plan only, JSON errors, revoke takes effect at once.
    data = api("/api/v1/renewals?days=7", secrets_made[0]).get_json()
    names = [item["name"] for item in data["items"]]
    assert names == [f"Owner plan {RUN}"], names
    assert data["items"][0]["amount"] == "260000.00" and data["items"][0]["days_left"] == 2
    assert api("/api/v1/renewals", "st_" + "x" * 43).get_json() == {"error": "bad-token"}
    with app.app_context():
        first_id = ApiToken.query.filter_by(token_hash=api_tokens.hash_secret(secrets_made[0])).one().id
    owner.post(f"/settings/tokens/{first_id}/revoke")
    owner.post(f"/settings/tokens/{first_id}/revoke")  # twice is harmless
    assert api("/api/v1/me", secrets_made[0]).get_json() == {"error": "revoked"}
    assert other.post(f"/settings/tokens/{first_id}/revoke").status_code == 404
    results["api_owner_only_revoke_now"] = True

    # Several revoked tokens (slot NULL) can live side by side: the filter ignores NULLs.
    with app.app_context():
        second = ApiToken.query.filter_by(token_hash=api_tokens.hash_secret(secrets_made[1])).one().id
    owner.post(f"/settings/tokens/{second}/revoke")
    assert [make_token(owner, f"Again {n}")[0] for n in range(3)] == [200, 200, 409]
    results["revoked_slots_reused"] = True

    # Expiry, at DATETIME2(0) precision.
    with app.app_context():
        token = ApiToken.query.filter_by(token_hash=api_tokens.hash_secret(secrets_made[2])).one()
        token.expires_at = utcnow().replace(microsecond=0) - timedelta(seconds=1)
        db.session.commit()
    assert api("/api/v1/me", secrets_made[2]).get_json() == {"error": "expired"}
    results["expired_refused"] = True

    # Real parallel connections: eight creates for a fresh account make exactly five.
    racer = app.test_client()
    sign_up(racer, f"tokens-race-{RUN}@example.com", username=f"tok_race_{RUN}")
    with app.app_context():
        racer_id = User.query.filter_by(email=f"tokens-race-{RUN}@example.com").one().id
    outcomes = []

    def create_one(n):
        with app.app_context():
            token, _ = api_tokens.create(db.session.get(User, racer_id), f"Thread {n}", 30, ["renewals:read"])
            outcomes.append(token is not None)
            db.session.remove()

    threads = [threading.Thread(target=create_one, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with app.app_context():
        slots = sorted(t.slot for t in ApiToken.query.filter(ApiToken.user_id == racer_id, ApiToken.slot.isnot(None)))
    assert outcomes.count(True) == 5 and slots == [1, 2, 3, 4, 5], (outcomes, slots)
    results["parallel_creates"] = {"created": outcomes.count(True), "refused": outcomes.count(False)}

    # A password reset disconnects every extension.
    with app.app_context():
        raw = tokens.issue(db.session.get(User, owner_id), "reset_password", 30)
    owner.post(f"/reset-password/{raw}", data={"password": "NewPassword456!", "confirm": "NewPassword456!"})
    with app.app_context():
        assert ApiToken.query.filter(ApiToken.user_id == owner_id, ApiToken.revoked_at.is_(None)).count() == 0
    assert api("/api/v1/me", secrets_made[3]).get_json() == {"error": "revoked"}
    results["password_reset_revokes"] = True

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    return results


if __name__ == "__main__":
    report = {"run": RUN, "migrations": migrate(), "application": application_checks()}
    out = ROOT / "instance" / "sql-api-tokens.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
