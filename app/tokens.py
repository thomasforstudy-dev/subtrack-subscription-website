"""One-time email links (confirm email, reset password).

The link holds a long random token. We store only its hash, an expiry time,
and when it was used, so each link works once and only for a short time.
"""

import hashlib
import secrets
from datetime import timedelta

from app import db
from app.models import AuthToken, User, utcnow


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(user: User, purpose: str, minutes: int) -> str:
    """Make a new token and return the raw value to put in the email link."""
    raw = secrets.token_urlsafe(32)
    db.session.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_hash(raw),
            email=user.email,
            expires_at=utcnow() + timedelta(minutes=minutes),
        )
    )
    db.session.commit()
    return raw


def find_valid(raw: str, purpose: str) -> AuthToken | None:
    """The token row if it can still be used, otherwise None."""
    if not raw or len(raw) > 200:
        return None
    token = AuthToken.query.filter_by(token_hash=_hash(raw), purpose=purpose).first()
    if token is None or token.used_at is not None or token.expires_at <= utcnow():
        return None
    # A link sent to an old address must not confirm a new one.
    if token.user is None or token.user.email != token.email:
        return None
    return token


def use(raw: str, purpose: str) -> User | None:
    """Use the token up and return its user, or None if it isn't valid.

    The UPDATE only succeeds while used_at is still empty, so if the link is
    clicked twice at the same moment, only one click wins.
    """
    token = find_valid(raw, purpose)
    if token is None:
        return None
    won = (
        AuthToken.query.filter_by(id=token.id, used_at=None)
        .update({"used_at": utcnow()}, synchronize_session=False)
    )
    if won != 1:
        db.session.rollback()
        return None
    db.session.commit()
    return db.session.get(User, token.user_id)


def cancel_all(user: User, purpose: str) -> None:
    """Make every unused link of this kind stop working (e.g. after a reset)."""
    AuthToken.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update(
        {"used_at": utcnow()}, synchronize_session=False
    )
    db.session.commit()
