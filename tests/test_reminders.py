"""The reminder job. Emails go to a list (or a fake), never to real people."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app import db, mailer, reminders
from app.mailer import MailError
from app.models import Reminder, Renewal, Subscription, User, utcnow


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield app


def make_user(email="me@example.com", verified=True, tz="UTC", hour=9, **extra):
    user = User(email=email, username=email.split("@")[0], timezone=tz, reminder_hour=hour,
                email_verified_at=utcnow() if verified else None, **extra)
    user.set_password("Password123!")
    db.session.add(user)
    db.session.commit()
    return user


def make_sub(user, renewal=date(2026, 11, 10), leads="7", **extra):
    sub = Subscription(user_id=user.id, name="Netflix", amount=Decimal("9.99"), currency="USD",
                       cycle="monthly", next_renewal_at=renewal, billing_day=renewal.day,
                       lead_days=leads, remind_days=int(leads.split(",")[0]), **extra)
    db.session.add(sub)
    db.session.commit()
    return sub


def at(text):  # "2026-11-03 09:00" in UTC
    return datetime.fromisoformat(text)


# ---------- when reminders go out --------------------------------------------

def test_sends_once_when_the_time_comes(ctx):
    make_sub(make_user())
    assert reminders.run(at("2026-11-03 08:59"))["planned"] == 0  # 7 days before, but before 9:00
    counts = reminders.run(at("2026-11-03 09:00"))
    assert counts["planned"] == 1 and counts["sent"] == 1
    assert "Netflix renews in 7 days" in mailer.sent[0].subject
    # Running again (every hour) doesn't send it again.
    reminders.run(at("2026-11-03 10:00"))
    assert len(mailer.sent) == 1


def test_each_lead_time_gets_its_own_reminder(ctx):
    make_sub(make_user(), leads="14,7,3")
    for day in ["2026-10-27", "2026-11-03", "2026-11-07"]:
        reminders.run(at(f"{day} 09:00"))
    assert [m.subject.split(" renews ")[1].split(" (")[0] for m in mailer.sent] == [
        "in 14 days", "in 7 days", "in 3 days",
    ]


def test_added_late_sends_only_the_closest(ctx):
    make_sub(make_user(), leads="14,7,3")
    counts = reminders.run(at("2026-11-08 09:00"))  # 2 days before
    assert counts["sent"] == 1 and counts["skipped_old"] == 2
    assert "in 2 days" in mailer.sent[0].subject
    assert Reminder.query.filter_by(status="skipped").count() == 2


def test_uses_the_users_time_zone(ctx):
    make_sub(make_user(tz="Asia/Ho_Chi_Minh", hour=9))  # 9:00 in Vietnam = 02:00 UTC
    reminders.run(at("2026-11-03 01:59"))
    assert mailer.sent == []
    reminders.run(at("2026-11-03 02:00"))
    assert len(mailer.sent) == 1


@pytest.mark.parametrize(
    "user_kwargs, sub_kwargs",
    [
        ({"verified": False}, {}),
        ({"reminders_enabled": False}, {}),
        ({"reminder_channels": ""}, {}),
        ({}, {"status": "archived"}),
    ],
)
def test_no_reminder_when_not_wanted(ctx, user_kwargs, sub_kwargs):
    make_sub(make_user(**user_kwargs), **sub_kwargs)
    reminders.run(at("2026-11-03 09:00"))
    assert mailer.sent == []


def test_changed_date_skips_the_old_reminder(ctx):
    sub = make_sub(make_user())
    reminders.run(at("2026-11-03 09:00"), dry_run=True)  # planned, not sent
    sub.next_renewal_at = date(2026, 12, 10)
    db.session.commit()
    counts = reminders.run(at("2026-11-03 09:05"))
    assert counts["skipped"] == 1 and mailer.sent == []


# ---------- failures, retries, crashes ---------------------------------------

def test_failed_send_is_retried_later_with_the_same_key(ctx, monkeypatch):
    make_sub(make_user())
    keys = []

    def flaky(email):
        keys.append(email.idempotency_key)
        if len(keys) == 1:
            raise MailError("Couldn't reach Resend (HTTP 503).")
        mailer.sent.append(email)

    monkeypatch.setattr(reminders, "send_email", flaky)
    assert reminders.run(at("2026-11-03 09:00"))["failed"] == 1
    row = Reminder.query.one()
    assert row.status == "failed" and row.attempts == 1 and "503" in row.last_error

    assert reminders.run(at("2026-11-03 09:05"))["sent"] == 0  # waits before retrying
    assert reminders.run(at("2026-11-03 09:15"))["sent"] == 1
    assert keys[0] == keys[1] == f"subtrack-reminder-{row.id}"
    assert Reminder.query.one().status == "sent"


def test_gives_up_after_max_attempts(ctx, monkeypatch):
    make_sub(make_user())

    def broken(email):
        raise MailError("HTTP 500")

    monkeypatch.setattr(reminders, "send_email", broken)
    now = at("2026-11-03 09:00")
    for _ in range(reminders.MAX_ATTEMPTS + 2):
        reminders.run(now)
        now += timedelta(days=1)
    assert Reminder.query.one().attempts == reminders.MAX_ATTEMPTS


def test_retry_preserves_message_and_sender_settings(ctx, monkeypatch):
    from dataclasses import asdict

    user = make_user()
    sub = make_sub(user)
    monkeypatch.setenv("MAIL_FROM", "first@example.com")
    monkeypatch.setenv("MAIL_REPLY_TO", "first-reply@example.com")
    messages = []

    def send(email):
        messages.append(asdict(email))
        if len(messages) == 1:
            raise MailError("Fake timeout after provider acceptance")

    monkeypatch.setattr(reminders, "send_email", send)
    assert reminders.run(at("2026-11-03 09:00"))["failed"] == 1
    sub.name = "Changed name"
    user.username = "changed_user"
    db.session.commit()
    monkeypatch.setenv("MAIL_FROM", "second@example.com")
    monkeypatch.setenv("MAIL_REPLY_TO", "second-reply@example.com")
    monkeypatch.setenv("SITE_URL", "https://changed.example.com")
    assert reminders.run(at("2026-11-04 08:00"))["sent"] == 1
    assert messages[0] == messages[1]


def test_real_planning_query_compiles_valid_sql_server_boolean(ctx):
    from sqlalchemy import event
    from sqlalchemy.dialects import mssql

    statements = []
    session = db.session()

    def capture(state):
        if state.is_select:
            statements.append(str(state.statement.compile(dialect=mssql.dialect())))

    event.listen(session, "do_orm_execute", capture)
    try:
        reminders.plan(at("2026-11-03 09:00"))
    finally:
        event.remove(session, "do_orm_execute", capture)
    sql = "\n".join(statements)
    assert "users.reminders_enabled = 1" in sql
    assert "users.reminders_enabled IS 1" not in sql


@pytest.mark.parametrize("date_text,hours", [
    ("2026-03-08", (6, 7)),
    ("2026-11-01", (5, 6)),
])
def test_dst_transition_does_not_duplicate_a_reminder(ctx, date_text, hours):
    day = date.fromisoformat(date_text)
    make_sub(make_user(tz="America/New_York", hour=2 if day.month == 3 else 1), renewal=day, leads="0")
    for hour in hours:
        reminders.run(datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=30))
    assert len(mailer.sent) == 1
    assert Reminder.query.filter_by(status="sent").count() == 1


def test_email_not_set_up_leaves_reminders_waiting(ctx, monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "none")
    make_sub(make_user())
    counts = reminders.run(at("2026-11-03 09:00"))
    assert counts["stopped"]
    row = Reminder.query.one()
    assert row.status == "pending" and row.attempts == 0


def test_two_runs_cannot_claim_the_same_reminder(ctx):
    make_sub(make_user())
    now = at("2026-11-03 09:00")
    reminders.run(now, dry_run=True)
    first_view = Reminder.query.one()
    second_view = Reminder(id=first_view.id, status=first_view.status,
                           attempts=first_view.attempts, claim_token=first_view.claim_token)
    assert reminders.claim(first_view, now) is not None
    assert reminders.claim(second_view, now) is None


def test_abandoned_send_is_picked_up_again(ctx):
    make_sub(make_user())
    now = at("2026-11-03 09:00")
    reminders.run(now, dry_run=True)
    reminders.claim(Reminder.query.one(), now)  # a run claimed it, then crashed
    assert reminders.run(now + timedelta(minutes=5))["sent"] == 0
    assert reminders.run(now + timedelta(minutes=20))["sent"] == 1


# ---------- moving dates forward ----------------------------------------------

def test_passed_dates_move_forward_and_keep_history(ctx):
    user = make_user()
    sub = make_sub(user, renewal=date(2028, 1, 31))
    counts = reminders.run(at("2028-03-15 09:00"))
    assert counts["rolled"] == 1
    assert db.session.get(Subscription, sub.id).next_renewal_at == date(2028, 3, 31)
    history = Renewal.query.order_by(Renewal.due_date).all()
    assert [r.due_date for r in history] == [date(2028, 1, 31), date(2028, 2, 29)]
    assert all(r.status == "expected" for r in history)  # not proof of payment
    reminders.run(at("2028-03-15 10:00"))
    assert Renewal.query.count() == 2


# ---------- the email and the command ----------------------------------------

def test_email_has_the_useful_links(ctx, monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://subtrack.example")
    make_sub(make_user(), manage_url="https://netflix.com/cancel")
    reminders.run(at("2026-11-03 09:00"))
    text = mailer.sent[0].text
    assert "9.99 USD" in text
    assert "https://netflix.com/cancel" in text
    assert "https://subtrack.example/settings" in text
    assert "not a confirmed payment" in text


def test_command_line(app):
    with app.app_context():
        make_sub(make_user(), renewal=date.today() + timedelta(days=3), leads="7")
    result = app.test_cli_runner().invoke(args=["send-reminders", "--dry-run"])
    assert result.exit_code == 0
    assert "planned: 1" in result.output
    assert mailer.sent == []
