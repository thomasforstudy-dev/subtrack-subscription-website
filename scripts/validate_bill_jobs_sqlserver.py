"""Check migration 07 and bill-reading jobs on the synthetic SQL Server test database.

Run from the repo folder:  .venv\\Scripts\\python scripts\\validate_bill_jobs_sqlserver.py
Uses Codex's allowlisted helpers (scripts/validate_sqlserver.py): only the
synthetic database SubTrack_CodexBills_20261019_Clean, Windows login, never the
app's .env and never the real SubTrack database. Adds only synthetic rows
(@example.com) and leaves them for inspection. No DROP/TRUNCATE, no email, no OCR.
"""

import json
import os
import sys
from datetime import datetime, timedelta
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
    tables = {row[0] for row in connection.execute("SELECT name FROM sys.tables")}
    uniques = {row[0] for row in connection.execute("SELECT name FROM sys.key_constraints WHERE type='UQ'")}
    for name in ("document_jobs", "document_pages", "bill_drafts", "bill_draft_revisions"):
        assert name in tables, name
    for name in ("UQ_document_jobs_document", "UQ_document_pages_once", "UQ_bill_drafts_job", "UQ_bill_draft_revisions_number"):
        assert name in uniques, name
    connection.close()
    return {"database": DATABASE, "scripts": [s.name for s in scripts], "passes": 2}


def application_checks() -> dict:
    with patch("dotenv.load_dotenv", return_value=False):
        # Import the test helpers FIRST: tests/conftest.py sets DATABASE_URL to an
        # in-memory SQLite database when it is imported.
        from tests.conftest import CSRFClient, sign_up
        from tests.test_bill_jobs import RECEIPT_LINES, docx, start_workers
        from app import create_app, db
        from app.models import Bill, BillDraft, Document, DocumentJob, DocumentPage, utcnow
        from app.schema import schema_issues
        from sqlalchemy.exc import IntegrityError
        os.environ.update(DB_SERVER="", DATABASE_URL="mssql+pyodbc:///?odbc_connect=" + quote_plus(dsn(DATABASE)),
                          APP_ENV="development", SECRET_KEY="sql-bill-jobs-test-secret-longer-than-32-chars",
                          MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="", SUBBY_PROVIDER="fake",
                          OCR_PROVIDER="")
        app = create_app()
    app.config.update(TESTING=True)
    app.test_client_class = CSRFClient
    results = {}
    with app.app_context():
        # Prove where we are: the synthetic SQL Server database, not SQLite.
        assert db.engine.dialect.name == "mssql", db.engine.dialect.name
        results["database"] = db.session.execute(db.text("SELECT DB_NAME()")).scalar()
        assert results["database"] == DATABASE
        results["schema_issues"] = schema_issues(db.engine)
        assert results["schema_issues"] == [], results["schema_issues"]

    def new_document(client, name):
        client.post("/bills/upload", data={"file": (__import__("io").BytesIO(docx(RECEIPT_LINES + [name])), name)},
                    content_type="multipart/form-data")
        with app.app_context():
            return Document.query.filter_by(original_name=name).order_by(Document.id.desc()).first().id

    owner = app.test_client()
    sign_up(owner, f"jobs-owner-{RUN}@example.com", username=f"jobs_owner_{RUN}")
    other = app.test_client()
    sign_up(other, f"jobs-other-{RUN}@example.com", username=f"jobs_other_{RUN}")

    # Duplicate requests -> one job; the database refuses a second job row too.
    doc_id = new_document(owner, f"receipt-{RUN}.docx")
    owner.post(f"/bills/files/{doc_id}/read")
    owner.post(f"/bills/files/{doc_id}/read")
    with app.app_context():
        job = DocumentJob.query.filter_by(document_id=doc_id).one()
        try:
            db.session.add(DocumentJob(user_id=job.user_id, document_id=doc_id))
            db.session.commit()
            raise AssertionError("second job for one document was accepted")
        except IntegrityError:
            db.session.rollback()
        job_id = job.id
    results["duplicate_requests_one_job"] = True

    # Two real processes race for the job: exactly one draft.
    now = utcnow().replace(microsecond=0)
    database_url = os.environ["DATABASE_URL"]
    outcomes = start_workers(database_url, app.instance_path, job_id, now.isoformat(), ["normal", "normal"])
    assert sorted(outcomes) == ["lost", "succeeded"], outcomes
    with app.app_context():
        assert BillDraft.query.filter_by(job_id=job_id).count() == 1
        assert DocumentPage.query.filter_by(document_id=doc_id).count() == 1
        draft_id = BillDraft.query.filter_by(job_id=job_id).one().id
    results["process_race_one_draft"] = outcomes

    # A worker process crash is recovered after STALE_AFTER without duplicates.
    doc2 = new_document(owner, f"crash-{RUN}.docx")
    owner.post(f"/bills/files/{doc2}/read")
    with app.app_context():
        job2 = DocumentJob.query.filter_by(document_id=doc2).one().id
    start_workers(database_url, app.instance_path, job2, now.isoformat(), ["crash_after_claim"], expect_crash=True)
    later = (now + timedelta(minutes=11)).isoformat()
    assert start_workers(database_url, app.instance_path, job2, later, ["normal"]) == ["succeeded"]
    with app.app_context():
        assert BillDraft.query.filter_by(job_id=job2).count() == 1
        assert db.session.get(DocumentJob, job2).attempts == 2
    results["crash_recovered"] = True

    # Someone else gets 404 everywhere.
    for path in (f"/bills/jobs/{job_id}", f"/bills/drafts/{draft_id}"):
        assert other.get(path).status_code == 404, path
    assert other.post(f"/bills/drafts/{draft_id}", data={"action": "accept", "revision": "1"}).status_code == 404
    results["other_user_blocked"] = True

    # Accept twice -> one bill, exact Decimal, evidence in the export.
    form = {"revision": "1", "action": "accept", "category": "food"}
    owner.post(f"/bills/drafts/{draft_id}", data=form)
    owner.post(f"/bills/drafts/{draft_id}", data=form)
    with app.app_context():
        draft = db.session.get(BillDraft, draft_id)
        bills = Bill.query.filter_by(document_id=doc_id).all()
        assert len(bills) == 1 and draft.status == "accepted" and draft.bill_id == bills[0].id
        assert str(bills[0].total) == "99000.00" and bills[0].currency == "VND"
        bill_id = bills[0].id
    rows = json.loads(owner.get("/bills/export.json").data)
    row = next(r for r in rows if r["id"] == bill_id)
    assert row["evidence"]["total"][0]["text"] == "99.000"
    results["accept_once_decimal_evidence"] = True

    # A rejected accept leaves the draft and makes no bill.
    with app.app_context():
        draft2 = BillDraft.query.filter_by(job_id=job2).one().id
    owner.post(f"/bills/drafts/{draft2}", data={"revision": "1", "action": "accept", "currency": "dollars"})
    with app.app_context():
        assert db.session.get(BillDraft, draft2).status == "draft"
        assert Bill.query.filter_by(document_id=doc2).count() == 0
    results["rejected_accept_no_change"] = True

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    return results


if __name__ == "__main__":
    report = {"run": RUN, "migrations": migrate(), "application": application_checks()}
    out = ROOT / "instance" / "sql-bill-jobs.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
