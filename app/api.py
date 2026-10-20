"""The Chrome extension's API: /api/v1/..., JSON only, for a valid token only.

It never looks at the login cookie. A request is allowed only with
"Authorization: Bearer st_..." for a token that is not expired or revoked and
has the scope the route needs, checked again on every request. That is also
why it needs no CSRF token: another website can't know the secret.
Contract: docs/CONTRACT.md -> Extension API tokens.

Limits are kept in memory in the one waitress process (like the login limits),
so they are not multiplied by extra workers: 120 requests per hour per token,
20 failed token checks per 10 minutes per address.
"""

import os
import re
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from flask import Blueprint, jsonify, request

from app import api_tokens
from app.models import Subscription, utcnow
from app.schedule import local_now, passed_renewals, user_zone
from app.security import RateLimiter, client_ip

bp = Blueprint("api", __name__, url_prefix="/api/v1")

requests_per_token = RateLimiter(120, 60 * 60)
failed_checks_per_ip = RateLimiter(20, 10 * 60)
MAX_DAYS = 31
CENT = Decimal("0.01")
EXTENSION_ORIGIN_SHAPE = re.compile(r"chrome-extension://[a-p]{32}")


def problem(code: str, status: int, retry_after: int = 0):
    """A JSON error, never a login page: {"error": "bad-token"}."""
    response = jsonify(error=code)
    response.status_code = status
    if status == 401:
        response.headers["WWW-Authenticate"] = 'Bearer realm="AllOutFree"'
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
    return response


def bearer_secret() -> str | None:
    """The secret from "Authorization: Bearer st_...".

    None when there is no header at all, "" when it is malformed: another
    scheme, extra spaces, two credentials, or not the shape of our secrets.
    The secret is never read from the address, a form or a cookie.
    """
    header = request.headers.get("Authorization")
    if header is None:
        return None
    scheme, _, secret = header.partition(" ")
    if scheme.lower() != "bearer" or not api_tokens.SECRET_SHAPE.fullmatch(secret):
        return ""
    return secret


def token_required(scope: str | None = None):
    """Run the view only for a valid token (with `scope`); the view gets the token."""

    def decorator(view):
        @wraps(view)
        def checked(*args, **kwargs):
            address = client_ip()
            if failed_checks_per_ip.is_blocked(address):
                return problem("slow-down", 429, failed_checks_per_ip.retry_after(address))
            secret = bearer_secret()
            if secret is None:
                return problem("missing-token", 401)
            now = utcnow()
            token = api_tokens.find(secret)
            status = "bad-token" if token is None else api_tokens.state(token, now)
            if status != "active":  # bad-token, expired or revoked
                failed_checks_per_ip.hit(address)
                return problem(status, 401)
            if scope and scope not in token.scope_list:
                return problem("missing-scope", 403)
            key = str(token.id)
            if not requests_per_token.hit(key):
                return problem("slow-down", 429, requests_per_token.retry_after(key))
            api_tokens.touch(token, now)
            return view(token, *args, **kwargs)

        return checked

    return decorator


def utc_text(moment) -> str:
    """A stored UTC time as text that says so, e.g. "2027-01-18T09:30:00Z"."""
    return moment.replace(microsecond=0).isoformat() + "Z"


@bp.get("/me")
@token_required()
def me(token):
    user = token.user
    return jsonify(
        username=user.username, timezone=user_zone(user.timezone).key,
        scopes=token.scope_list, expires_at=utc_text(token.expires_at),
    )


@bp.get("/renewals")
@token_required("renewals:read")
def renewals(token):
    """The owner's active plans renewing from today until (not including) today + days."""
    raw = request.args.get("days", "7")
    if not re.fullmatch(r"[0-9]{1,2}", raw) or not 1 <= int(raw) <= MAX_DAYS:
        return problem("bad-days", 400)
    days = int(raw)
    user = token.user
    today = local_now(user.timezone).date()  # "today" where the owner lives
    end = today + timedelta(days=days)
    items = []
    for sub in Subscription.query.filter_by(user_id=user.id, status="active"):
        # The saved date can be in the past until the reminder job moves it on;
        # work out the real next date without changing anything.
        _, due = passed_renewals(sub.next_renewal_at, sub.cycle, sub.billing_day, today)
        if due < end:
            items.append({
                "id": sub.id, "name": sub.name, "amount": str(Decimal(sub.amount).quantize(CENT)),
                "currency": sub.currency, "next_renewal_at": due.isoformat(), "days_left": (due - today).days,
            })
    # Soonest first; no limit, so a badge built from "count" never undercounts.
    items.sort(key=lambda item: (item["next_renewal_at"], item["name"].casefold(), item["id"]))
    return jsonify(
        today=today.isoformat(), timezone=user_zone(user.timezone).key, days=days,
        count=len(items), items=items,
    )


def extension_origin() -> str:
    """The extension's exact origin from .env (EXTENSION_ORIGIN), or "" if unset or not valid."""
    origin = os.getenv("EXTENSION_ORIGIN", "").strip()
    return origin if EXTENSION_ORIGIN_SHAPE.fullmatch(origin) else ""


@bp.after_request
def api_headers(response):
    response.headers["Cache-Control"] = "no-store"  # private data: never kept by browsers or Cloudflare
    response.vary.add("Origin")
    allowed = extension_origin()
    # CORS only lets that one origin's pages read the answer. It is not the
    # login: the token is. No cookies are ever allowed (no Allow-Credentials).
    if allowed and request.headers.get("Origin") == allowed:
        response.headers["Access-Control-Allow-Origin"] = allowed
        if request.method == "OPTIONS":  # the browser's "may I send this?" question
            response.headers["Access-Control-Allow-Methods"] = "GET"
            response.headers["Access-Control-Allow-Headers"] = "Authorization"
            response.headers["Access-Control-Max-Age"] = "600"
    return response
