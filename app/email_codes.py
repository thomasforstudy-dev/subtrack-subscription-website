"""The 6-digit code in the "confirm your email" email.

Like the email links (app/tokens.py), only a hash is stored and a code works
once, for a short time, for the address it was sent to. Codes live in their own
table so a code can never be used as a link. Only the newest code works.
"""

import hashlib
import secrets
from datetime import timedelta

from app import db
from app.models import EmailCode, User, utcnow

MINUTES = 30


def _hash(user: User, code: str) -> str:
    # The user id is part of what's hashed, so the same 6 digits mean
    # nothing for another account.
    return hashlib.sha256(f"{user.id}:{code}".encode()).hexdigest()


def cancel_all(user: User) -> None:
    """Make every unused code stop working."""
    EmailCode.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": utcnow()}, synchronize_session=False
    )
    db.session.commit()


def issue(user: User) -> str:
    """A new code for this user; older codes stop working. Returns the code."""
    cancel_all(user)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.session.add(EmailCode(user_id=user.id, code_hash=_hash(user, code), email=user.email,
                             expires_at=utcnow() + timedelta(minutes=MINUTES)))
    db.session.commit()
    return code


def use(user: User, code: str) -> bool:
    """True if the code is right, still valid, for the current address, and the
    newest code this account was sent.

    "Newest" is checked here, not only by cancelling old codes in issue(): two
    "send again" clicks at the same moment could each cancel and then each add
    a code, leaving two unused ones. Only the last one counts.
    The UPDATE only succeeds while used_at is still empty, so a code used
    twice at the same moment works only once.
    """
    now = utcnow()
    newest = EmailCode.query.filter_by(user_id=user.id).order_by(EmailCode.id.desc()).first()
    if newest is None or newest.code_hash != _hash(user, code):
        return False
    won = (
        EmailCode.query.filter(
            EmailCode.id == newest.id, EmailCode.email == user.email,
            EmailCode.used_at.is_(None), EmailCode.expires_at > now,
        ).update({"used_at": now}, synchronize_session=False)
    )
    db.session.commit()
    return won == 1
