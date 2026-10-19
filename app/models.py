"""Database tables.

The SQL Server versions of these tables are created by the numbered scripts
in database/ (01_schema.sql, 02_accounts.sql, ...). If you change a column
here, add a new script there too. Old SQLite files are upgraded by app/migrate.py.
"""

import hashlib
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Unicode(30), unique=True, nullable=False)
    email = db.Column(db.Unicode(255), unique=True, nullable=False)
    password_hash = db.Column(db.Unicode(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)
    email_verified_at = db.Column(db.DateTime)  # empty until they click the email link
    # Reminder settings (the /settings page).
    timezone = db.Column(db.Unicode(64), default="UTC", nullable=False)
    reminders_enabled = db.Column(db.Boolean, default=True, nullable=False)
    reminder_hour = db.Column(db.Integer, default=9, nullable=False)  # local hour, 0-23
    reminder_channels = db.Column(db.Unicode(60), default="email", nullable=False)  # "email,extension"

    subscriptions = db.relationship(
        "Subscription", backref="owner", lazy=True, passive_deletes=True
    )
    links = db.relationship("Link", backref="owner", lazy=True, passive_deletes=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def session_key(self) -> str:
        """A short fingerprint of the password hash.

        It is saved in the login cookie next to the user id. Changing the
        password changes the fingerprint, so every other browser that was
        logged in to this account is logged out.
        """
        return hashlib.sha256(self.password_hash.encode()).hexdigest()[:16]

    def get_id(self) -> str:
        return f"{self.id}:{self.session_key}"

    @property
    def channel_list(self) -> list[str]:
        return [c for c in (self.reminder_channels or "").split(",") if c]


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    CYCLES = ("weekly", "monthly", "yearly")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.Unicode(120), nullable=False)
    amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    currency = db.Column(db.Unicode(8), default="USD", nullable=False)
    cycle = db.Column(db.Unicode(20), default="monthly", nullable=False)
    next_renewal_at = db.Column(db.Date, nullable=False, default=date.today)
    # The day of the month it really bills on (31), so short months don't
    # make the date drift (see app/schedule.py).
    billing_day = db.Column(db.Integer)
    # Kept for older pages and the SQL views: the biggest number in lead_days.
    remind_days = db.Column(db.Integer, default=7, nullable=False)
    lead_days = db.Column(db.Unicode(40), default="7", nullable=False)  # "14,7,3"
    manage_url = db.Column(db.Unicode(2048), default="", nullable=False)  # where to cancel/manage
    status = db.Column(db.Unicode(20), default="active", nullable=False)
    notes = db.Column(db.UnicodeText, default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def lead_list(self) -> list[int]:
        """[14, 7, 3]: how many days before the renewal to remind, biggest first."""
        days = {int(d) for d in (self.lead_days or "").split(",") if d.strip().isdigit()}
        return sorted(days, reverse=True)


class Renewal(db.Model):
    """A renewal date that has passed: an *expected* charge, not a proven one.

    The reminder job writes one row each time it moves a subscription to its
    next date, so the history isn't lost. status stays "expected" until the
    user (or a confirmed bill, later) says "paid" or "skipped".
    """

    __tablename__ = "renewals"
    __table_args__ = (
        db.UniqueConstraint("subscription_id", "due_date", name="UQ_renewals_once"),
    )

    STATUSES = ("expected", "paid", "skipped")

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, nullable=False)  # copy of the owner, for simple filtering
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.Unicode(8), nullable=False)
    status = db.Column(db.Unicode(20), default="expected", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Reminder(db.Model):
    """One reminder to send: this renewal, this many days before, this channel.

    The unique key means a reminder can be *planned* only once, even if two
    copies of the job run at the same time. `status` moves:
    pending -> sending -> sent, or -> failed (tried again later), or skipped.
    """

    __tablename__ = "reminders"
    __table_args__ = (
        db.UniqueConstraint(
            "subscription_id", "renewal_date", "channel", "lead_days", name="UQ_reminders_once"
        ),
    )

    STATUSES = ("pending", "sending", "sent", "failed", "skipped")

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, nullable=False)
    renewal_date = db.Column(db.Date, nullable=False)
    lead_days = db.Column(db.Integer, nullable=False)
    channel = db.Column(db.Unicode(20), default="email", nullable=False)
    status = db.Column(db.Unicode(20), default="pending", nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    next_try_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    claimed_at = db.Column(db.DateTime)
    claim_token = db.Column(db.Unicode(32))
    sent_at = db.Column(db.DateTime)
    last_error = db.Column(db.Unicode(200), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    subscription = db.relationship("Subscription")


class ReminderLog(db.Model):
    """Not used any more: replaced by Reminder (several lead times per renewal).
    Kept so the table and any old rows stay as they are."""

    __tablename__ = "reminder_logs"
    __table_args__ = (
        db.UniqueConstraint(
            "subscription_id", "renewal_date", "channel", name="UQ_reminder_once"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    subscription_id = db.Column(
        db.Integer,
        db.ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    renewal_date = db.Column(db.Date, nullable=False)
    sent_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    channel = db.Column(db.Unicode(20), default="email", nullable=False)
    result = db.Column(db.Unicode(40), default="pending", nullable=False)


class AuthToken(db.Model):
    """A one-time link sent by email: "confirm your email" or "reset your password".

    Only a SHA-256 hash of the token is stored, so someone who reads the
    database still can't use the links.
    """

    __tablename__ = "auth_tokens"

    PURPOSES = ("verify_email", "reset_password")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose = db.Column(db.Unicode(20), nullable=False)
    token_hash = db.Column(db.Unicode(64), unique=True, nullable=False)
    email = db.Column(db.Unicode(255), nullable=False)  # the address the link was sent to
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    user = db.relationship("User")


class Link(db.Model):
    """A website the user saved so they don't lose it."""

    __tablename__ = "links"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    url = db.Column(db.Unicode(2048), nullable=False)
    title = db.Column(db.Unicode(200), nullable=False)
    tags = db.Column(db.Unicode(200), default="", nullable=False)
    notes = db.Column(db.UnicodeText, default="", nullable=False)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @property
    def tag_list(self) -> list[str]:
        return [t for t in (self.tags or "").split(", ") if t]

    @property
    def hostname(self) -> str:
        return urlparse(self.url).netloc
