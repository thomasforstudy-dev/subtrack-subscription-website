"""Database tables.

The SQL Server versions of these tables are created by database/01_schema.sql.
If you change a column here, change it there too.
"""

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
    email = db.Column(db.Unicode(255), unique=True, nullable=False)
    password_hash = db.Column(db.Unicode(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    subscriptions = db.relationship(
        "Subscription", backref="owner", lazy=True, passive_deletes=True
    )
    links = db.relationship("Link", backref="owner", lazy=True, passive_deletes=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


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
    remind_days = db.Column(db.Integer, default=7, nullable=False)
    status = db.Column(db.Unicode(20), default="active", nullable=False)
    notes = db.Column(db.UnicodeText, default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class ReminderLog(db.Model):
    """One row per reminder sent, so the same renewal is never emailed twice."""

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
