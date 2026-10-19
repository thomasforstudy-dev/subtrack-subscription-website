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

from app import db
from app.auth import create_user, finish_login
from app.mailer import external_url
from app.models import User, utcnow
from app.security import safe_next_url

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
    return external_url("oauth.callback", provider=provider)


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
    session["oauth_next"] = safe_next_url(request.args.get("next"))
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

    next_url = session.pop("oauth_next", None)
    user = User.query.filter_by(email=email).first()
    if user is None:
        user = create_user(email, verified=True)
    elif not user.email_verified:
        take_over_unverified(user)
    return finish_login(user, next_url)


def take_over_unverified(user: User) -> None:
    """Google/GitHub just proved this person owns the email, but the account
    was made with a password and never confirmed.

    Someone else could have signed up with this email first and set a password
    they know, waiting for the real owner to move in. So that password is
    switched off. The owner can set their own with "Forgot password".
    """
    user.set_password(secrets.token_urlsafe(32))  # also logs out other browsers
    user.email_verified_at = utcnow()
    db.session.commit()
    flash("Your email is now confirmed. To log in with a password too, use \"Forgot password\".")


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
