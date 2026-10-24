"""Small security helpers used all over the app.

- CSRF tokens: forms that change something must prove they came from our pages.
- client_ip(): the visitor's real address, even behind Cloudflare Tunnel.
- RateLimiter: "at most N tries per X minutes" (login, Subby, emails).
- safe_next_url(): only redirect to pages on this site after logging in.
"""

import ipaddress
import math
import os
import secrets
import threading
import time
from urllib.parse import urlparse

from flask import abort, request, session

CSRF_FIELD = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# /subby/ask only accepts JSON (which other websites can't send without our
# permission) and never changes anyone's account (its tools only read, or
# prepare a form the user must submit), so it needs no token.
CSRF_EXEMPT = {"subby.ask"}


def csrf_token() -> str:
    """The secret for this browser session, put in every form as a hidden field."""
    if CSRF_FIELD not in session:
        session[CSRF_FIELD] = secrets.token_urlsafe(32)
    return session[CSRF_FIELD]


def check_csrf() -> None:
    """Runs before every request.

    Another website could make a visitor's browser submit a form to us (for
    example "delete this link"), and the browser would send the login cookie
    along. That website can't read our pages, so it can't know the token.
    """
    if request.method not in UNSAFE_METHODS or request.endpoint in CSRF_EXEMPT:
        return
    expected = session.get(CSRF_FIELD)
    sent = request.form.get(CSRF_FIELD) or request.headers.get(CSRF_HEADER) or ""
    if not expected or not secrets.compare_digest(expected, sent):
        abort(400, description="This page expired. Please go back, reload it and try again.")


def trusted_proxies() -> set[str]:
    raw = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1")
    return {part.strip() for part in raw.split(",") if part.strip()}


def client_ip() -> str:
    """The visitor's real address.

    Cloudflare Tunnel runs on this PC, so every request seems to come from
    127.0.0.1, and Cloudflare puts the real address in CF-Connecting-IP.
    Anyone can *send* that header, so we only believe it when the request
    really came from a trusted proxy.
    """
    remote = request.remote_addr or "unknown"
    forwarded = request.headers.get("CF-Connecting-IP", "").strip()
    if forwarded and remote in trusted_proxies():
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass  # not a real address: ignore it
    return remote


_all_limiters: list["RateLimiter"] = []


class RateLimiter:
    """Allow at most `limit` events per `window` seconds for each key.

    Kept in memory: it resets when the server restarts and only counts within
    one server process. That fits SubTrack (one waitress process on one PC).
    """

    MAX_KEYS = 10_000  # a hard cap on remembered keys, so memory can't grow forever

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()  # waitress answers several requests at once
        _all_limiters.append(self)

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.limit

    def hit(self, key: str) -> bool:
        """Count one event. Returns False (and doesn't count it) if over the limit."""
        with self._lock:
            now = time.monotonic()
            if len(self._hits) >= self.MAX_KEYS and key not in self._hits:
                for old_key in list(self._hits):
                    self._recent(old_key, now)  # first drop keys whose window is over
                while len(self._hits) >= self.MAX_KEYS:
                    # Still full (e.g. a flood of new IPs): forget the key that was
                    # quiet the longest. Memory stays bounded; that key starts fresh.
                    quietest = min(self._hits, key=lambda k: self._hits[k][-1])
                    del self._hits[quietest]
            recent = self._recent(key, now)
            if len(recent) >= self.limit:
                return False
            self._hits[key] = recent + [now]
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again (for the Retry-After header); 0 = now."""
        with self._lock:
            now = time.monotonic()
            recent = self._recent(key, now)
            if len(recent) < self.limit:
                return 0
            # The oldest event leaves the window first; then there is room again.
            return max(1, math.ceil(self.window - (now - recent[0])))

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


def security_headers(response):
    """Runs after every request (registered in app/__init__.py).

    - Pages for a logged-in user are private: browsers and proxies must not keep
      a copy (Cache-Control: no-store), so the next person on a shared computer
      can't press Back to see them.
    - nosniff, no framing and a sensible Referrer-Policy on everything.
    setdefault keeps any stricter header a route already set (file downloads,
    the calendar, the API)."""
    from flask_login import current_user

    if not request.path.startswith("/static/") and current_user.is_authenticated:
        response.headers.setdefault("Cache-Control", "no-store, private")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def clear_all_limits() -> None:
    """Used by the tests, so one test's tries don't count against the next."""
    for limiter in _all_limiters:
        limiter.clear()


def safe_next_url(target: str | None) -> str | None:
    """Return `target` only if it is a page on this site, like "/links/".

    Without this check, a link such as /login?next=https://evil.example would
    send people to another website right after they log in.
    """
    if not target or not target.startswith("/") or target.startswith("//"):
        return None
    if "\\" in target or any(ord(ch) < 32 for ch in target):
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    return target
