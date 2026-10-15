"""Sign in with Google or GitHub (OAuth 2.0 "authorization code" flow).

1. /auth/<provider> sends the visitor to Google/GitHub with a random `state`.
2. They approve, and Google/GitHub send them back to /auth/<provider>/callback
   with a one-time `code`.
3. We swap the code for an access token, ask for their *verified* email,
   then log them in (making an account the first time).
"""

import os
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, abort, flash, redirect, request, session, url_for

from app.auth import create_user, finish_login
from app.models import User

bp = Blueprint("oauth", __name__)

PROVIDERS = {
    "google": {
        "name": "Google",
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "openid email",
    },
    "github": {
        "name": "GitHub",
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "user:email",
    },
}
TIMEOUT = 10  # seconds to wait for Google/GitHub


def credentials(provider: str) -> tuple[str, str] | None:
    """Client ID and secret from .env, e.g. GOOGLE_CLIENT_ID, or None if not set."""
    prefix = provider.upper()
    client_id = os.getenv(f"{prefix}_CLIENT_ID", "").strip()
    secret = os.getenv(f"{prefix}_CLIENT_SECRET", "").strip()
    return (client_id, secret) if client_id and secret else None


def enabled_providers() -> list[dict]:
    """Only show buttons for providers the owner has set up."""
    return [
        {"key": key, "name": info["name"]}
        for key, info in PROVIDERS.items()
        if credentials(key)
    ]


def callback_url(provider: str) -> str:
    # SITE_URL (e.g. https://alloutdeepclean.com) is needed behind Cloudflare,
    # because this server itself only sees plain http://127.0.0.1.
    base = os.getenv("SITE_URL", "").strip().rstrip("/") or request.host_url.rstrip("/")
    return base + url_for("oauth.callback", provider=provider)


def provider_or_404(provider: str) -> tuple[dict, tuple[str, str]]:
    creds = credentials(provider) if provider in PROVIDERS else None
    if creds is None:
        abort(404)
    return PROVIDERS[provider], creds


@bp.route("/auth/<provider>")
def start(provider):
    info, (client_id, _) = provider_or_404(provider)
    # A random value we check on the way back, so nobody can trick a user
    # into logging in with someone else's account (CSRF).
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    params = {
        "client_id": client_id,
        "redirect_uri": callback_url(provider),
        "response_type": "code",
        "scope": info["scope"],
        "state": state,
    }
    if provider == "google":
        params["prompt"] = "select_account"
    return redirect(info["authorize_url"] + "?" + urlencode(params))


@bp.route("/auth/<provider>/callback")
def callback(provider):
    info, creds = provider_or_404(provider)
    expected = session.pop("oauth_state", None)
    got = request.args.get("state", "")
    code = request.args.get("code")
    if not expected or not secrets.compare_digest(expected, got) or not code:
        flash(f"{info['name']} sign-in was cancelled or expired. Please try again.")
        return redirect(url_for("auth.login"))

    try:
        token = get_access_token(provider, code, creds)
        email = get_verified_email(provider, token)
    except (requests.RequestException, KeyError, ValueError):
        email = None
    if not email:
        flash(f"We couldn't get a verified email from {info['name']}. Please try another way.")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first() or create_user(email)
    return finish_login(user)


def get_access_token(provider: str, code: str, creds: tuple[str, str]) -> str:
    client_id, secret = creds
    res = requests.post(
        PROVIDERS[provider]["token_url"],
        data={
            "client_id": client_id,
            "client_secret": secret,
            "code": code,
            "redirect_uri": callback_url(provider),
            "grant_type": "authorization_code",
        },
        headers={"Accept": "application/json"},  # GitHub replies in JSON only if asked
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def get_verified_email(provider: str, token: str) -> str | None:
    headers = {"Authorization": f"Bearer {token}"}
    if provider == "google":
        res = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo", headers=headers, timeout=TIMEOUT
        )
        res.raise_for_status()
        info = res.json()
        ok = info.get("email") and info.get("email_verified")
        return info["email"].strip().lower() if ok else None

    # GitHub: a person can have several emails; use the primary, verified one.
    res = requests.get(
        "https://api.github.com/user/emails",
        headers={**headers, "Accept": "application/vnd.github+json"},
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    for item in res.json():
        if item.get("primary") and item.get("verified"):
            return item["email"].strip().lower()
    return None
