"""Actual separate processes claim one shared synthetic SQLite reminder."""

import multiprocessing
import sqlite3
from datetime import datetime

from tests.reminder_worker import worker


def planned_reminder(app):
    from app import db, reminders
    from app.models import Reminder
    from tests.test_reminders import make_sub, make_user

    with app.app_context():
        make_sub(make_user())
        reminders.run(datetime(2026, 11, 3, 9), dry_run=True)
        return str(db.engine.url), Reminder.query.one().id


def start_workers(database_url, item_id, now, modes, provider, expected_crash=False):
    context = multiprocessing.get_context("spawn")
    ready, results = context.Queue(), context.Queue()
    start = context.Event()
    processes = [context.Process(target=worker, args=(database_url, item_id, now, mode,
                 ready, start, results, str(provider))) for mode in modes]
    try:
        for process in processes:
            process.start()
        for _ in processes:
            assert ready.get(timeout=40) == "ready"
        start.set()
        outcomes = [] if expected_crash else [results.get(timeout=40) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == (17 if expected_crash else 0)
        return outcomes
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
        ready.close()
        results.close()


def provider_database(tmp_path):
    path = tmp_path / "fake-provider.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE deliveries (idempotency_key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    return path


def test_two_processes_only_one_claim_and_one_fake_delivery(app, tmp_path):
    database_url, item_id = planned_reminder(app)
    provider = provider_database(tmp_path)
    outcomes = start_workers(database_url, item_id, "2026-11-03T09:00:00", ["normal", "normal"], provider)
    assert sorted(outcomes) == ["lost", "sent"]
    with sqlite3.connect(provider) as conn:
        assert conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 1


def test_crash_after_send_can_retry_same_payload_next_day(app, tmp_path):
    from app.models import Reminder

    database_url, item_id = planned_reminder(app)
    provider = provider_database(tmp_path)
    start_workers(database_url, item_id, "2026-11-03T09:00:00", ["crash_after_send"], provider, expected_crash=True)
    with app.app_context():
        assert Reminder.query.one().status == "sending"
    assert start_workers(database_url, item_id, "2026-11-04T08:00:00", ["normal"], provider) == ["sent"]
    with sqlite3.connect(provider) as conn:
        assert conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0] == 1
