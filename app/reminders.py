"""Reminder emails. Run by Windows Task Scheduler, never inside a web request:

    .venv\\Scripts\\python -m flask --app app send-reminders

Each run does four steps:
1. roll:  a renewal date that has passed moves to the next one, and the old
          date is saved in `renewals` as an *expected* charge (not a payment).
2. plan:  for each "remind me N days before" that is due, add one `reminders`
          row. The unique key (subscription, renewal date, channel, N) means
          two runs at the same time can't plan the same reminder twice.
3. claim: take a row with a conditional UPDATE. Only one run can win it.
4. send:  email it with an idempotency key, then mark it sent, or failed to
          try again later with a growing wait.

If the server crashes between sending and marking "sent", the row is claimed
again after STALE_AFTER and sent with the *same* idempotency key, so Resend
drops the repeat (Resend remembers keys for 24 hours). That makes duplicates
very unlikely, but no email system can promise "exactly once".
"""

import json
import logging
import os
import secrets
from dataclasses import asdict
from datetime import datetime, time, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import and_, or_, true
from sqlalchemy.exc import IntegrityError

from app import db, mailer
from app.mailer import Email, MailError, MailNotReady, external_url, send_email
from app.models import Reminder, Renewal, Subscription, User, utcnow
from app.schedule import local_now, passed_renewals

log = logging.getLogger(__name__)

CHANNELS = ("email",)  # "extension" and "calendar" come later (Codex)
MAX_ATTEMPTS = 5
STALE_AFTER = timedelta(minutes=15)  # a "sending" row older than this was abandoned
BATCH = 100


class StopSending(Exception):
    """Email isn't set up: stop this run and leave the rows waiting."""


# ---------- 1. roll ----------------------------------------------------------

def roll_forward(now: datetime) -> int:
    """Move passed renewal dates forward and keep the history. Returns how many moved."""
    moved = 0
    # Nobody's local "today" is more than a day ahead of UTC's.
    cutoff = now.date() + timedelta(days=1)
    rows = (
        db.session.query(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .filter(Subscription.status == "active", Subscription.next_renewal_at <= cutoff)
        .all()
    )
    for sub, user in rows:
        today = local_now(user.timezone, now).date()
        passed, upcoming = passed_renewals(sub.next_renewal_at, sub.cycle, sub.billing_day, today)
        if not passed:
            continue
        for due in passed:
            if not Renewal.query.filter_by(subscription_id=sub.id, due_date=due).first():
                db.session.add(Renewal(
                    subscription_id=sub.id, user_id=sub.user_id, due_date=due,
                    amount=sub.amount, currency=sub.currency,
                ))
        sub.next_renewal_at = upcoming
        try:
            db.session.commit()
            moved += 1
        except IntegrityError:  # another run did the same at the same moment
            db.session.rollback()
    return moved


# ---------- 2. plan ----------------------------------------------------------

def due_leads(sub: Subscription, user: User, now: datetime) -> list[int]:
    """The "N days before" milestones whose time has come, closest first."""
    here = local_now(user.timezone, now)
    if here.date() > sub.next_renewal_at:
        return []  # already passed: the roll step will move it
    send_at = time(hour=max(0, min(user.reminder_hour, 23)))
    due = []
    for lead in sub.lead_list:
        moment = datetime.combine(sub.next_renewal_at - timedelta(days=lead), send_at, here.tzinfo)
        if here >= moment:
            due.append(lead)
    return sorted(due)


def plan(now: datetime) -> tuple[int, int]:
    """Add reminder rows that are due. Returns (planned, skipped)."""
    planned = skipped = 0
    rows = (
        db.session.query(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .filter(
            Subscription.status == "active",
            User.reminders_enabled == true(),  # SQL Server BIT uses = 1, never IS 1
            User.email_verified_at.isnot(None),  # only confirmed addresses get email
        )
        .all()
    )
    for sub, user in rows:
        leads = due_leads(sub, user, now)
        if not leads:
            continue
        for channel in [c for c in user.channel_list if c in CHANNELS]:
            for lead in leads:
                exists = Reminder.query.filter_by(
                    subscription_id=sub.id, renewal_date=sub.next_renewal_at,
                    channel=channel, lead_days=lead,
                ).first()
                if exists:
                    continue
                # Several milestones due at once (e.g. added 2 days before
                # renewal with 14, 7, 3): send only the closest, skip the rest.
                status = "pending" if lead == leads[0] else "skipped"
                db.session.add(Reminder(
                    subscription_id=sub.id, user_id=user.id, renewal_date=sub.next_renewal_at,
                    lead_days=lead, channel=channel, status=status, next_try_at=now,
                ))
                try:
                    db.session.commit()
                except IntegrityError:  # another run planned it first
                    db.session.rollback()
                    continue
                if status == "pending":
                    planned += 1
                else:
                    skipped += 1
    return planned, skipped


# ---------- 3. claim ---------------------------------------------------------

def claim(reminder: Reminder, now: datetime) -> str | None:
    """Take the row for this run. Returns our claim token, or None if another run has it."""
    token = secrets.token_hex(8)
    still_same = and_(
        Reminder.id == reminder.id,
        Reminder.status == reminder.status,
        Reminder.attempts == reminder.attempts,
        Reminder.claim_token.is_(None) if reminder.claim_token is None
        else Reminder.claim_token == reminder.claim_token,
    )
    won = Reminder.query.filter(still_same).update(
        {"status": "sending", "claim_token": token, "claimed_at": now},
        synchronize_session=False,
    )
    db.session.commit()
    return token if won == 1 else None


def waiting(now: datetime) -> list[Reminder]:
    return (
        Reminder.query.filter(
            or_(
                and_(Reminder.status == "pending", Reminder.next_try_at <= now),
                and_(Reminder.status == "failed", Reminder.attempts < MAX_ATTEMPTS,
                     Reminder.next_try_at <= now),
                and_(Reminder.status == "sending", Reminder.claimed_at < now - STALE_AFTER),
            )
        )
        .order_by(Reminder.id)
        .limit(BATCH)
        .all()
    )


# ---------- 4. send ----------------------------------------------------------

def finish(reminder_id: int, token: str, **values) -> None:
    """Save the result, but only if we still hold the claim."""
    Reminder.query.filter_by(id=reminder_id, claim_token=token).update(
        {**values, "claim_token": None}, synchronize_session=False
    )
    db.session.commit()


def build_email(reminder: Reminder, sub: Subscription, user: User, now: datetime) -> Email:
    days_left = (sub.next_renewal_at - local_now(user.timezone, now).date()).days
    when = "today" if days_left == 0 else ("tomorrow" if days_left == 1 else f"in {days_left} days")
    lines = [
        f"Hi {user.username},",
        "",
        f"{sub.name} is expected to renew {when}, on {sub.next_renewal_at:%a %d %b %Y}, "
        f"for {sub.amount} {sub.currency}.",
        "",
        "Renew or cancel it before then if you need to.",
    ]
    if sub.manage_url:
        lines += ["", f"Manage it here: {sub.manage_url}"]
    lines += [
        "",
        f"See it in AllOutFree: {external_url('subscriptions.edit', item_id=sub.id)}",
        "",
        "AllOutFree can't see your bank: this date is what you told us, not a confirmed payment.",
        f"Change or turn off reminders: {external_url('settings.show')}",
    ]
    return Email(
        to=user.email,
        subject=f"{sub.name} renews {when} ({sub.amount} {sub.currency})",
        text="\n".join(lines),
        idempotency_key=f"subtrack-reminder-{reminder.id}",  # same key on every retry
    )


def deliver(reminder: Reminder, token: str, now: datetime) -> str:
    sub = db.session.get(Subscription, reminder.subscription_id)
    user = db.session.get(User, reminder.user_id)
    still_wanted = (
        sub is not None and user is not None
        and sub.user_id == user.id
        and sub.status == "active"
        and sub.next_renewal_at == reminder.renewal_date  # the date wasn't changed since
        and user.reminders_enabled and user.email_verified
        and reminder.channel in user.channel_list
    )
    if not still_wanted:
        finish(reminder.id, token, status="skipped")
        return "skipped"

    try:
        email = saved_email(reminder, token, sub, user, now)
        if email is None:
            return "skipped"  # the claim expired, or the recipient changed
        send_email(email)
    except MailNotReady as exc:
        # Not the reminder's fault: put it back without counting a try.
        finish(reminder.id, token, status="pending")
        raise StopSending(str(exc)) from exc
    except MailError as exc:
        attempts = reminder.attempts + 1
        finish(
            reminder.id, token, status="failed", attempts=attempts,
            last_error=str(exc)[:200],
            next_try_at=now + timedelta(minutes=5 * 2 ** attempts),  # 10, 20, 40, 80 min
        )
        return "failed"
    finish(reminder.id, token, status="sent", sent_at=now, attempts=reminder.attempts + 1, last_error="")
    return "sent"


def saved_email(reminder: Reminder, token: str, sub: Subscription, user: User, now: datetime) -> Email | None:
    """Freeze the entire message before the first send, including sender settings.

    A provider may have accepted an email before our process died. Reusing its
    idempotency key only works when the retry also sends the identical payload.
    """
    if reminder.payload_json is None:
        # Freeze only when it can really be sent now. Freezing while email is
        # off would save an empty sender, and the reminder would stay stuck.
        if not mailer.mail_ready():
            raise MailNotReady("Email sending isn't set up (MAIL_BACKEND / RESEND_API_KEY).")
        if mailer.backend() == "resend" and not (
            os.getenv("RESEND_API_KEY", "").strip() and os.getenv("MAIL_FROM", "").strip()
        ):
            raise MailNotReady("RESEND_API_KEY and MAIL_FROM must both be set.")
        email = build_email(reminder, sub, user, now)
        email.sender = os.getenv("MAIL_FROM", "").strip()
        email.reply_to = os.getenv("MAIL_REPLY_TO", "").strip()
        won = Reminder.query.filter_by(id=reminder.id, claim_token=token).filter(
            Reminder.payload_json.is_(None)
        ).update({"payload_json": json.dumps(asdict(email), ensure_ascii=False)}, synchronize_session=False)
        db.session.commit()
        if won != 1:
            return None
        db.session.refresh(reminder)
    if reminder.claim_token != token:
        return None
    email = Email(**json.loads(reminder.payload_json))
    if email.to != user.email:
        finish(reminder.id, token, status="skipped")
        return None
    return email


def send_due(now: datetime) -> dict:
    counts = {"sent": 0, "failed": 0, "skipped": 0, "stopped": ""}
    for reminder in waiting(now):
        token = claim(reminder, now)
        if token is None:
            continue  # another run took it
        try:
            result = deliver(reminder, token, now)
        except StopSending as exc:
            counts["stopped"] = str(exc)
            break
        counts[result] += 1
    return counts


def run(now: datetime | None = None, dry_run: bool = False) -> dict:
    now = now or utcnow()
    counts = {"rolled": roll_forward(now)}
    counts["planned"], counts["skipped_old"] = plan(now)
    if not dry_run:
        site = os.getenv("SITE_URL", "").strip() or "http://localhost"
        # Links in the emails need a web address even though this isn't a web request.
        with current_app.test_request_context(base_url=site):
            counts.update(send_due(now))
    return counts


@click.command("send-reminders")
@click.option("--dry-run", is_flag=True, help="Roll dates and plan reminders, but send nothing.")
@with_appcontext
def send_reminders_command(dry_run: bool):
    """Send the reminder emails that are due. Safe to run every 15-60 minutes."""
    counts = run(dry_run=dry_run)
    click.echo(", ".join(f"{key}: {value}" for key, value in counts.items() if value != ""))
    if counts.get("stopped"):
        raise click.ClickException("Email isn't set up, so nothing was sent: " + counts["stopped"])
