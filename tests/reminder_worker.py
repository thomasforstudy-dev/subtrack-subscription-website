"""Spawn-safe worker. No app imports or dotenv reads happen at module import."""

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from unittest.mock import patch


def worker(database_url, reminder_id, now_text, mode, ready, start, results, provider_path):
    os.environ.update(DB_SERVER="", DATABASE_URL=database_url, APP_ENV="development",
                      SECRET_KEY="process-test-secret-longer-than-thirty-two-characters",
                      MAIL_BACKEND="memory", RESEND_API_KEY="", GEMINI_API_KEY="",
                      SUBBY_PROVIDER="fake", SITE_URL="https://preview.example.test")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import create_app, db, reminders
        from app.mailer import MailError
        from app.models import Reminder

        app = create_app()
    now = datetime.fromisoformat(now_text)

    def fake_send(email):
        payload = json.dumps(asdict(email), sort_keys=True)
        with sqlite3.connect(provider_path, timeout=20) as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT payload FROM deliveries WHERE idempotency_key=?",
                                    (email.idempotency_key,)).fetchone()
            if existing and existing[0] != payload:
                raise MailError("Fake provider: same idempotency key with a different payload")
            conn.execute("INSERT OR IGNORE INTO deliveries VALUES (?, ?)", (email.idempotency_key, payload))
        if mode == "crash_after_send":
            os._exit(17)

    reminders.send_email = fake_send
    try:
        with app.app_context():
            row = db.session.get(Reminder, reminder_id)
            ready.put("ready")
            if not start.wait(30):
                raise RuntimeError("Worker start timed out")
            token = reminders.claim(row, now)
            outcome = "lost"
            if token:
                with app.test_request_context(base_url="https://preview.example.test"):
                    outcome = reminders.deliver(row, token, now)
            results.put(outcome)
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
