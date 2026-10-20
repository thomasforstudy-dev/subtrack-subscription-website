"""API tokens for the Chrome extension: the owner's pages (create, list, revoke)
and the checks app/api.py runs on every extension request.

Contract agreed with Codex: docs/proposals/2026-10-20-codex-extension-token-response.md;
routes and fields: docs/CONTRACT.md -> Extension API tokens.

The secret ("st_" + 43 random characters) is shown once, on the page that
created it, and never again: only its SHA-256 hash is stored. It never goes in
a flash message either, because flash messages travel in the login cookie.
"""

import hashlib
import re
import secrets
from datetime import timedelta

from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ApiToken, User, utcnow
from app.schedule import local_now

bp = Blueprint("api_tokens", __name__)

SECRET_START = "st_"
SECRET_SHAPE = re.compile(r"st_[A-Za-z0-9_-]{43}")  # secrets.token_urlsafe(32) is 43 characters
# What a token may see: (Vietnamese, English) labels. Version 1 has one scope.
SCOPES = {"renewals:read": ("Xem các gói sắp gia hạn", "See the plans that renew soon")}
MAX_ACTIVE = 5
DEFAULT_DAYS, MAX_DAYS = 90, 365
NAME_MAX = 60
TOUCH_EVERY = timedelta(minutes=1)


def hash_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def state(token: ApiToken, now=None) -> str:
    """"active", "expired" or "revoked"."""
    now = now or utcnow()
    if token.revoked_at is not None:
        return "revoked"
    if token.expires_at <= now:
        return "expired"
    return "active"


def free_expired_slots(user_id: int, now) -> None:
    """Expired tokens no longer count towards the five: give their slots back."""
    ApiToken.query.filter(
        ApiToken.user_id == user_id, ApiToken.slot.isnot(None), ApiToken.expires_at <= now
    ).update({"slot": None}, synchronize_session=False)
    db.session.commit()


def used_slots(user_id: int) -> set[int]:
    rows = db.session.query(ApiToken.slot).filter(ApiToken.user_id == user_id, ApiToken.slot.isnot(None))
    return {slot for (slot,) in rows}


def create(user: User, name: str, days: int, scopes: list[str]) -> tuple[ApiToken | None, str]:
    """Make a token; return it with its secret, or (None, "") when all five slots are taken.

    Two requests can pick the same free slot at the same moment. The database
    then refuses the second one (unique index on user + slot), and it looks
    for another free slot, so there can never be a sixth active token.
    """
    now = utcnow()
    free_expired_slots(user.id, now)
    for _ in range(MAX_ACTIVE):
        free = [n for n in range(1, MAX_ACTIVE + 1) if n not in used_slots(user.id)]
        if not free:
            return None, ""
        raw = SECRET_START + secrets.token_urlsafe(32)
        token = ApiToken(
            user_id=user.id, name=name, token_hash=hash_secret(raw), prefix=raw[:8],
            scopes=",".join(scopes), slot=free[0], created_at=now, expires_at=now + timedelta(days=days),
        )
        db.session.add(token)
        try:
            db.session.commit()
            return token, raw
        except IntegrityError:
            db.session.rollback()  # another request took that slot first: look again
    return None, ""


def find(raw: str) -> ApiToken | None:
    """The token with this secret, in any state, or None."""
    if not SECRET_SHAPE.fullmatch(raw or ""):
        return None
    return ApiToken.query.filter_by(token_hash=hash_secret(raw)).first()


def touch(token: ApiToken, now) -> None:
    """Remember when it was last used, but write at most once a minute per token."""
    ApiToken.query.filter(
        ApiToken.id == token.id,
        or_(ApiToken.last_used_at.is_(None), ApiToken.last_used_at <= now - TOUCH_EVERY),
    ).update({"last_used_at": now}, synchronize_session=False)
    db.session.commit()


def revoke_all(user: User) -> None:
    """After a password reset every extension has to connect again.
    The caller commits, together with the new password."""
    ApiToken.query.filter_by(user_id=user.id, revoked_at=None).update(
        {"revoked_at": utcnow(), "slot": None}, synchronize_session=False
    )


# ---------- the owner's pages (login cookie + CSRF, like every form) ----------

def local_date(moment):
    """A stored UTC time as the owner's local date, for the list."""
    return local_now(current_user.timezone, moment).date() if moment else None


def page(new_secret: str = "", status: int = 200):
    now = utcnow()
    tokens = (
        ApiToken.query.filter_by(user_id=current_user.id)
        .order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
        .all()
    )
    rows = [(token, state(token, now)) for token in tokens]
    html = render_template(
        "api_tokens.html", rows=rows, active=sum(1 for _, s in rows if s == "active"),
        new_secret=new_secret, scopes=SCOPES, local_date=local_date,
        max_active=MAX_ACTIVE, default_days=DEFAULT_DAYS, max_days=MAX_DAYS, name_max=NAME_MAX,
    )
    response = make_response(html, status)
    response.headers["Cache-Control"] = "no-store"  # the page may show a secret
    return response


@bp.get("/settings/tokens")
@login_required
def list_tokens():
    return page()


@bp.post("/settings/tokens")
@login_required
def create_token():
    name = " ".join((request.form.get("name") or "").split())
    raw_days = (request.form.get("days") or str(DEFAULT_DAYS)).strip()
    scopes = sorted(set(request.form.getlist("scopes")))
    if not name or len(name) > NAME_MAX:
        flash(f"Give the token a name of up to {NAME_MAX} characters, like “Chrome on my laptop”.")
        return page(status=400)
    if not re.fullmatch(r"[0-9]{1,3}", raw_days) or not 1 <= int(raw_days) <= MAX_DAYS:
        flash(f"Pick how long it works: 1 to {MAX_DAYS} days.")
        return page(status=400)
    if not scopes or any(scope not in SCOPES for scope in scopes):
        flash("Pick what the token may see.")
        return page(status=400)
    token, raw = create(current_user, name, int(raw_days), scopes)
    if token is None:
        flash(f"You already have {MAX_ACTIVE} active tokens. Revoke one first.")
        return page(status=409)
    return page(new_secret=raw)


@bp.post("/settings/tokens/<int:token_id>/revoke")
@login_required
def revoke(token_id: int):
    token = ApiToken.query.filter_by(id=token_id, user_id=current_user.id).first_or_404()
    # Only the first click changes anything; clicking again is harmless.
    ApiToken.query.filter_by(id=token.id, revoked_at=None).update(
        {"revoked_at": utcnow(), "slot": None}, synchronize_session=False
    )
    db.session.commit()
    flash(f"“{token.name}” is revoked. The extension using it has to connect again.")
    return redirect(url_for("api_tokens.list_tokens"))
