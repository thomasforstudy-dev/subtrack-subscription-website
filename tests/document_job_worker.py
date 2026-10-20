"""Spawn-safe worker for the reading-job process tests (like reminder_worker.py).

No app imports or .env reads happen when this module is imported.
mode "normal": claim the job and run it. "crash_after_claim": claim it, then the
process dies on the spot (os._exit), leaving the job "running".
"""

import os
from datetime import datetime
from unittest.mock import patch


def worker(database_url, instance_path, job_id, now_text, mode, ready, start, results):
    os.environ.update(DB_SERVER="", DATABASE_URL=database_url, APP_ENV="development",
                      SECRET_KEY="process-test-secret-longer-than-thirty-two-characters",
                      MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="",
                      SUBBY_PROVIDER="fake", OCR_PROVIDER="")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import bill_jobs, create_app, db
        from app.models import DocumentJob

        app = create_app()
    app.instance_path = instance_path  # the uploaded file lives in the test's folder
    now = datetime.fromisoformat(now_text)
    try:
        with app.app_context():
            job = db.session.get(DocumentJob, job_id)
            ready.put("ready")
            if not start.wait(30):
                raise RuntimeError("Worker start timed out")
            token = bill_jobs.claim(job, now)
            if token is None:
                results.put("lost")
                return
            if mode == "crash_after_claim":
                os._exit(17)
            db.session.refresh(job)
            results.put(bill_jobs.run_job(job, token, now))
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
