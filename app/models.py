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
    # Persist before sending so a crash/retry uses exactly the same provider payload.
    payload_json = db.Column(db.UnicodeText)
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
    # Fingerprint of the cleaned-up address (see links.url_fingerprint), to
    # spot the same page saved twice. Empty for links saved before 04_links.sql.
    url_hash = db.Column(db.Unicode(64), index=True)
    favicon_url = db.Column(db.Unicode(2048), default="", nullable=False)  # the site's own icon

    @property
    def tag_list(self) -> list[str]:
        return [t for t in (self.tags or "").split(", ") if t]

    @property
    def hostname(self) -> str:
        try:
            return urlparse(self.url).netloc
        except ValueError:  # a broken address saved before links were checked
            return ""


class Document(db.Model):
    """A file the user uploaded (photo, PDF or Word file of a bill).

    The file itself lives in instance/uploads/ (never in static/), under a
    random name the server picks. original_name is only shown, never used
    as a path. The same file twice (same sha256) is kept once per user.
    """

    __tablename__ = "documents"
    __table_args__ = (db.UniqueConstraint("user_id", "sha256", name="UQ_documents_once"),)

    KINDS = ("png", "jpeg", "webp", "pdf", "docx")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    original_name = db.Column(db.Unicode(255), nullable=False)
    stored_name = db.Column(db.Unicode(64), unique=True, nullable=False)  # "<32 hex>.pdf"
    kind = db.Column(db.Unicode(10), nullable=False)  # found from the file's first bytes
    size_bytes = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.Unicode(64), nullable=False)
    page_count = db.Column(db.Integer)  # None = couldn't count (some PDFs)
    # "uploaded" for now; the OCR job adds queued/running/needs_review/... later.
    status = db.Column(db.Unicode(20), default="uploaded", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Bill(db.Model):
    """A receipt or a credit card bill, typed in or checked by the user.

    Every field the bill doesn't show stays empty (None), never guessed: a
    receipt without a time has transaction_time None, not 00:00.
    The full card number, PIN or OTP is never stored, only the last 4 digits.
    """

    __tablename__ = "bills"
    __table_args__ = (db.Index("IX_bills_user_date", "user_id", "status", "transaction_date"),)

    KINDS = ("receipt", "card_bill")
    STATUSES = ("confirmed", "archived")  # "draft" comes with OCR later
    CATEGORIES = (
        "software", "streaming", "education", "utilities",
        "shopping", "food", "travel", "other",
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))  # the uploaded file, if any
    kind = db.Column(db.Unicode(20), default="receipt", nullable=False)
    merchant = db.Column(db.Unicode(200), nullable=False)
    branch = db.Column(db.Unicode(200), default="", nullable=False)
    address = db.Column(db.Unicode(500), default="", nullable=False)
    invoice_number = db.Column(db.Unicode(64), default="", nullable=False)
    invoice_date = db.Column(db.Date)  # the date printed on the bill
    transaction_date = db.Column(db.Date)  # when the payment happened
    transaction_time = db.Column(db.Time)  # None when the bill shows no time
    timezone = db.Column(db.Unicode(64), default="", nullable=False)  # "" = not known
    currency = db.Column(db.Unicode(8), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2))
    tax = db.Column(db.Numeric(12, 2))
    total = db.Column(db.Numeric(12, 2))
    category = db.Column(db.Unicode(30), default="other", nullable=False)
    # Credit card bills only.
    card_last4 = db.Column(db.Unicode(4), default="", nullable=False)
    statement_start = db.Column(db.Date)
    statement_end = db.Column(db.Date)
    due_date = db.Column(db.Date)  # pay by this day
    paid_at = db.Column(db.Date)  # None = not paid yet
    notes = db.Column(db.UnicodeText, default="", nullable=False)
    source = db.Column(db.Unicode(20), default="manual", nullable=False)  # manual / upload
    status = db.Column(db.Unicode(20), default="confirmed", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    document = db.relationship("Document")
    lines = db.relationship(
        "BillLine", backref="bill", lazy=True, order_by="BillLine.position",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class BillLine(db.Model):
    """One line on a bill: "Coffee, 2 x 3.50"."""

    __tablename__ = "bill_lines"
    __table_args__ = (db.Index("IX_bill_lines_bill", "bill_id", "position"),)

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(
        db.Integer, db.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False
    )
    position = db.Column(db.Integer, nullable=False)  # 1, 2, 3 ... as on the bill
    description = db.Column(db.Unicode(300), nullable=False)
    quantity = db.Column(db.Numeric(10, 3))
    unit_price = db.Column(db.Numeric(12, 2))
    amount = db.Column(db.Numeric(12, 2))


# ---------- Reading uploaded bills (app/bill_jobs.py) --------------------------

class DocumentJob(db.Model):
    """"Read this bill for me": one job per uploaded file.

    status: queued -> running -> succeeded, or -> failed (error_code says why).
    Like reminders, a worker takes the job with a conditional UPDATE and a
    claim_token, so two workers can't both run it, and a worker that crashed
    leaves a "running" job that is picked up again after STALE_AFTER.
    """

    __tablename__ = "document_jobs"
    __table_args__ = (
        db.UniqueConstraint("document_id", name="UQ_document_jobs_document"),
        db.Index("IX_document_jobs_status", "status", "next_try_at"),
    )

    STATUSES = ("queued", "running", "succeeded", "failed")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    status = db.Column(db.Unicode(20), default="queued", nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    next_try_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    claim_token = db.Column(db.Unicode(32))
    claimed_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    error_code = db.Column(db.Unicode(40), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    document = db.relationship("Document")


class DocumentPage(db.Model):
    """The text read from one page of an uploaded file, exactly as read.

    Evidence in a draft points into this text (page + character positions),
    so it is stored once and never edited. A Word file is one "page".
    """

    __tablename__ = "document_pages"
    __table_args__ = (
        db.UniqueConstraint("document_id", "page_number", name="UQ_document_pages_once"),
    )

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)  # copy of the owner, for simple filtering
    page_number = db.Column(db.Integer, nullable=False)
    text = db.Column(db.UnicodeText, default="", nullable=False)
    source = db.Column(db.Unicode(20), nullable=False)  # pdf-text / docx / ocr
    engine = db.Column(db.Unicode(80), default="", nullable=False)  # OCR model + revision
    truncated = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class BillDraft(db.Model):
    """What was found on an uploaded bill, waiting for the owner to check it.

    Nothing here is a confirmed bill. extracted_json is what the reader found
    (never changed); values_json is the current form: for every field the value,
    where it came from ("document", "you" or "empty") and its evidence.
    Accepting creates a real Bill and links it in bill_id.
    """

    __tablename__ = "bill_drafts"
    __table_args__ = (db.UniqueConstraint("job_id", name="UQ_bill_drafts_job"),)

    STATUSES = ("draft", "accepted", "discarded")

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey("document_jobs.id"), nullable=False)
    status = db.Column(db.Unicode(20), default="draft", nullable=False)
    extractor = db.Column(db.Unicode(80), nullable=False)  # how the fields were found
    extracted_json = db.Column(db.UnicodeText, nullable=False)
    values_json = db.Column(db.UnicodeText, nullable=False)
    revision = db.Column(db.Integer, default=1, nullable=False)
    bill_id = db.Column(db.Integer, db.ForeignKey("bills.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    document = db.relationship("Document")
    job = db.relationship("DocumentJob")


class BillDraftRevision(db.Model):
    """One saved step of a draft: extracted, edited or accepted (the history)."""

    __tablename__ = "bill_draft_revisions"
    __table_args__ = (
        db.UniqueConstraint("draft_id", "number", name="UQ_bill_draft_revisions_number"),
    )

    id = db.Column(db.Integer, primary_key=True)
    draft_id = db.Column(
        db.Integer, db.ForeignKey("bill_drafts.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, nullable=False)
    number = db.Column(db.Integer, nullable=False)
    action = db.Column(db.Unicode(20), nullable=False)  # extracted / edited / accepted
    changed = db.Column(db.Unicode(400), default="", nullable=False)  # "total, merchant"
    values_json = db.Column(db.UnicodeText, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class ApiToken(db.Model):
    """A secret the Chrome extension sends instead of the login cookie.

    Like AuthToken, only a SHA-256 hash of the secret is stored. Each active
    token sits in one of five numbered slots. The unique index on
    (user_id, slot) is what stops a sixth token, even when two "create"
    requests arrive at the same moment. Revoked and expired tokens give their
    slot back (slot = NULL) and stay in the list; they are never deleted.
    """

    __tablename__ = "api_tokens"
    __table_args__ = (
        db.UniqueConstraint("token_hash", name="UQ_api_tokens_hash"),
        db.Index(
            "UX_api_tokens_user_slot", "user_id", "slot", unique=True,
            sqlite_where=db.text("slot IS NOT NULL"), mssql_where=db.text("slot IS NOT NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.Unicode(60), nullable=False)  # the owner's label, e.g. "Chrome on laptop"
    token_hash = db.Column(db.Unicode(64), nullable=False)
    prefix = db.Column(db.Unicode(12), nullable=False)  # first characters, to recognise it in the list
    scopes = db.Column(db.Unicode(200), nullable=False)  # comma list, e.g. "renewals:read"
    slot = db.Column(db.Integer)  # 1-5 while active, NULL once revoked or expired
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime)

    user = db.relationship("User")

    @property
    def scope_list(self) -> list[str]:
        return [s for s in (self.scopes or "").split(",") if s]
