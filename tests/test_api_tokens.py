"""Extension API tokens: the owner's pages and the token-only /api/v1/ API.

Contract: docs/CONTRACT.md -> Extension API tokens (agreed with Codex,
docs/proposals/2026-10-20-codex-extension-token-response.md).
"""

import hashlib
import logging
import re
import threading
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app import api, api_tokens, db, tokens
from app.models import ApiToken, Subscription, User, utcnow
from app.schedule import local_now, passed_renewals
from app.security import RateLimiter

from .conftest import PASSWORD, sign_up

SECRET = re.compile(r'value="(st_[A-Za-z0-9_-]{43})"')
ORIGIN = "chrome-extension://" + "a" * 32


def make_token(client, name="Chrome on laptop", days="90", scopes=("renewals:read",)):
    response = client.post("/settings/tokens", data={"name": name, "days": days, "scopes": list(scopes)})
    found = SECRET.search(response.get_data(as_text=True))
    return response, (found.group(1) if found else None)


def call(client, path, secret=None, headers=None):
    headers = dict(headers or {})
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    return client.get(path, headers=headers)


def add_plan(user_id, name, due, amount="9.99", currency="USD", cycle="monthly", status="active"):
    plan = Subscription(user_id=user_id, name=name, amount=Decimal(amount), currency=currency, cycle=cycle,
                        next_renewal_at=due, billing_day=due.day if cycle == "monthly" else None, status=status)
    db.session.add(plan)
    db.session.commit()
    return plan.id


def owner_id(email="a@example.com"):
    return User.query.filter_by(email=email).one().id


# ---------- the owner's pages ----------

def test_secret_is_shown_once_and_only_its_hash_is_stored(user, app):
    response, secret = make_token(user)
    assert response.status_code == 200 and secret
    assert response.headers["Cache-Control"] == "no-store"
    with app.app_context():
        row = ApiToken.query.one()
        assert row.token_hash == hashlib.sha256(secret.encode()).hexdigest()
        assert row.prefix == secret[:8] and row.slot == 1 and row.scope_list == ["renewals:read"]
        assert secret not in repr([getattr(row, c.name) for c in ApiToken.__table__.columns])
        assert (row.expires_at - row.created_at) == timedelta(days=90)
    listing = user.get("/settings/tokens")
    page = listing.get_data(as_text=True)
    assert listing.headers["Cache-Control"] == "no-store"
    assert secret not in page and f"{secret[:8]}…" in page  # the list shows the prefix only
    with user.session_transaction() as session:
        assert secret not in repr(dict(session))  # never in a flash message (they live in the cookie)


def test_token_pages_need_login_and_csrf(client, user):
    assert client.post("/settings/tokens", data={"name": "x", "days": "9", "scopes": "renewals:read"},
                       csrf=False).status_code == 400
    user.post("/logout")
    response = user.get("/settings/tokens")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


@pytest.mark.parametrize("form", [
    {"name": "", "days": "90", "scopes": "renewals:read"},
    {"name": "x" * 61, "days": "90", "scopes": "renewals:read"},
    {"name": "Chrome", "days": "0", "scopes": "renewals:read"},
    {"name": "Chrome", "days": "366", "scopes": "renewals:read"},
    {"name": "Chrome", "days": "abc", "scopes": "renewals:read"},
    {"name": "Chrome", "days": "90", "scopes": "links:read"},
    {"name": "Chrome", "days": "90"},
])
def test_bad_create_form_makes_no_token(user, app, form):
    assert user.post("/settings/tokens", data=form).status_code == 400
    with app.app_context():
        assert ApiToken.query.count() == 0


def test_settings_page_links_to_the_tokens(user):
    assert "/settings/tokens" in user.get("/settings").get_data(as_text=True)


# ---------- authentication ----------

def test_api_needs_the_token_never_the_cookie(user, app):
    with app.app_context():
        add_plan(owner_id(), "Netflix", local_now("UTC").date() + timedelta(days=2))
    _, secret = make_token(user)
    cookie_only = call(user, "/api/v1/renewals")  # logged in, but no token
    assert cookie_only.status_code == 401 and cookie_only.get_json() == {"error": "missing-token"}
    assert cookie_only.headers["WWW-Authenticate"].startswith("Bearer")
    stranger = app.test_client()  # no cookie at all, only the token
    answer = call(stranger, "/api/v1/renewals", secret)
    assert answer.status_code == 200 and [i["name"] for i in answer.get_json()["items"]] == ["Netflix"]
    assert answer.headers["Cache-Control"] == "no-store" and "Set-Cookie" not in answer.headers


@pytest.mark.parametrize("header", [
    "Basic {s}", "Bearer", "Bearer ", "{s}", "Bearer  {s}", "Bearer {s} ", "Bearer {s}x", "Bearer st_short",
    "Bearer {s}, Bearer {s}",  # two credentials (servers join repeated headers like this)
])
def test_malformed_authorization_is_refused(user, app, header):
    _, secret = make_token(user)
    response = call(app.test_client(), "/api/v1/renewals", headers={"Authorization": header.format(s=secret)})
    assert response.status_code == 401 and response.get_json() == {"error": "bad-token"}


def test_token_in_the_address_is_never_used(user, app):
    _, secret = make_token(user)
    for path in (f"/api/v1/renewals?access_token={secret}", f"/api/v1/renewals?token={secret}"):
        assert call(app.test_client(), path).get_json() == {"error": "missing-token"}


def test_unknown_revoked_and_expired_tokens(user, app, monkeypatch):
    _, secret = make_token(user)
    client = app.test_client()
    assert call(client, "/api/v1/me", "st_" + "x" * 43).get_json() == {"error": "bad-token"}
    with app.app_context():
        expires = ApiToken.query.one().expires_at
    monkeypatch.setattr(api, "utcnow", lambda: expires - timedelta(seconds=1))
    assert call(client, "/api/v1/me", secret).status_code == 200  # one second before: still fine
    monkeypatch.setattr(api, "utcnow", lambda: expires)
    assert call(client, "/api/v1/me", secret).get_json() == {"error": "expired"}  # at the exact moment: over
    monkeypatch.undo()
    with app.app_context():
        token_id = ApiToken.query.one().id
    user.post(f"/settings/tokens/{token_id}/revoke")
    assert call(client, "/api/v1/me", secret).get_json() == {"error": "revoked"}  # the very next request


def test_missing_scope_is_403(user, app):
    raw = "st_" + "s" * 43
    with app.app_context():
        db.session.add(ApiToken(user_id=owner_id(), name="no scope", token_hash=api_tokens.hash_secret(raw),
                                prefix=raw[:8], scopes="", slot=1, expires_at=utcnow() + timedelta(days=1)))
        db.session.commit()
    client = app.test_client()
    assert call(client, "/api/v1/renewals", raw).status_code == 403
    assert call(client, "/api/v1/renewals", raw).get_json() == {"error": "missing-scope"}
    assert call(client, "/api/v1/me", raw).status_code == 200  # /me needs no scope


def test_me_is_minimal(user, app):
    _, secret = make_token(user)
    data = call(app.test_client(), "/api/v1/me", secret).get_json()
    assert set(data) == {"username", "timezone", "scopes", "expires_at"}
    assert data["scopes"] == ["renewals:read"] and data["expires_at"].endswith("Z")


def test_unknown_api_address_is_json(app):
    response = app.test_client().get("/api/v1/nothing-here")
    assert response.status_code == 404 and response.get_json() == {"error": "not-found"}


# ---------- what the extension sees ----------

def test_only_my_active_plans_inside_the_window(client, app):
    sign_up(client, "other@example.com")
    with app.app_context():
        today = local_now("UTC").date()
        add_plan(owner_id("other@example.com"), "Their plan", today + timedelta(days=1))
    client.post("/logout")
    sign_up(client, "me@example.com")
    with app.app_context():
        me = owner_id("me@example.com")
        add_plan(me, "Spotify", today + timedelta(days=6), "59000", "VND")
        add_plan(me, "Netflix", today, "260000", "VND")
        add_plan(me, "Apple", today + timedelta(days=6), "0.99", "USD")
        add_plan(me, "Too late", today + timedelta(days=7))
        add_plan(me, "Archived", today + timedelta(days=2), status="archived")
    _, secret = make_token(client)
    data = call(app.test_client(), "/api/v1/renewals?days=7", secret).get_json()
    assert data["today"] == today.isoformat() and data["days"] == 7 and data["count"] == 3
    assert [(i["name"], i["days_left"], i["amount"], i["currency"]) for i in data["items"]] == [
        ("Netflix", 0, "260000.00", "VND"), ("Apple", 6, "0.99", "USD"), ("Spotify", 6, "59000.00", "VND"),
    ]
    assert set(data["items"][0]) == {"id", "name", "amount", "currency", "next_renewal_at", "days_left"}
    one_day = call(app.test_client(), "/api/v1/renewals?days=1", secret).get_json()
    assert [i["name"] for i in one_day["items"]] == ["Netflix"]  # today <= date < today + days


def test_today_is_the_owners_local_day(user, app, monkeypatch):
    # 18:30 UTC on 20 Oct is already 01:30 on 21 Oct in Ho Chi Minh City.
    moment = datetime(2026, 10, 20, 18, 30, tzinfo=timezone.utc)
    real = local_now
    monkeypatch.setattr(api, "local_now", lambda zone, now=None: real(zone, moment))
    with app.app_context():
        owner = User.query.one()
        owner.timezone = "Asia/Ho_Chi_Minh"
        db.session.commit()
        add_plan(owner.id, "Due on the 21st", date(2026, 10, 21))
        add_plan(owner.id, "Was due on the 20th", date(2026, 10, 20))  # passed there: next is 20 Nov
    _, secret = make_token(user)
    data = call(app.test_client(), "/api/v1/renewals?days=1", secret).get_json()
    assert data["today"] == "2026-10-21" and data["timezone"] == "Asia/Ho_Chi_Minh"
    assert [(i["name"], i["days_left"]) for i in data["items"]] == [("Due on the 21st", 0)]


def test_old_saved_dates_are_rolled_forward_without_writing(user, app):
    with app.app_context():
        today = local_now("UTC").date()
        stale = today - timedelta(days=21)
        plan_id = add_plan(owner_id(), "Weekly", stale, cycle="weekly")
    _, secret = make_token(user)
    data = call(app.test_client(), "/api/v1/renewals?days=7", secret).get_json()
    expected = passed_renewals(stale, "weekly", None, today)[1]
    assert [i["next_renewal_at"] for i in data["items"]] == [expected.isoformat()]
    with app.app_context():
        assert db.session.get(Subscription, plan_id).next_renewal_at == stale  # read-only


@pytest.mark.parametrize("days", ["0", "32", "abc", "7.5", "-1", "٣", ""])
def test_bad_days_is_400(user, app, days):
    _, secret = make_token(user)
    response = call(app.test_client(), f"/api/v1/renewals?days={days}", secret)
    assert response.status_code == 400 and response.get_json() == {"error": "bad-days"}


# ---------- revoking, the five-token limit, password reset ----------

def test_revoke_is_owner_scoped_and_safe_to_repeat(client, app):
    sign_up(client, "owner@example.com")
    _, secret = make_token(client)
    with app.app_context():
        token_id = ApiToken.query.one().id
    client.post("/logout")
    sign_up(client, "other@example.com")
    assert client.post(f"/settings/tokens/{token_id}/revoke").status_code == 404
    assert call(app.test_client(), "/api/v1/me", secret).status_code == 200  # still works
    client.post("/logout")
    client.post("/login", data={"identifier": "owner@example.com", "password": PASSWORD})
    assert client.post(f"/settings/tokens/{token_id}/revoke").status_code == 302
    with app.app_context():
        first = db.session.get(ApiToken, token_id).revoked_at
    assert first is not None
    assert client.post(f"/settings/tokens/{token_id}/revoke").status_code == 302
    with app.app_context():
        token = db.session.get(ApiToken, token_id)
        assert token.revoked_at == first and token.slot is None  # kept in the list, slot given back


def test_five_active_tokens_at_most(user, app):
    for n in range(5):
        assert make_token(user, name=f"Chrome {n}")[1]
    response, secret = make_token(user, name="Sixth")
    assert response.status_code == 409 and secret is None
    with app.app_context():
        first, second = ApiToken.query.order_by(ApiToken.id).limit(2).all()
        first_id = first.id
        second.expires_at = utcnow() - timedelta(seconds=1)  # expired tokens don't count either
        db.session.commit()
    assert make_token(user, name="After expiry")[1]
    user.post(f"/settings/tokens/{first_id}/revoke")
    assert make_token(user, name="After revoke")[1]
    assert make_token(user, name="Too many")[1] is None
    with app.app_context():
        slots = [t.slot for t in ApiToken.query.filter(ApiToken.slot.isnot(None))]
        assert sorted(slots) == [1, 2, 3, 4, 5]


def test_the_database_refuses_two_tokens_in_one_slot(user, app, monkeypatch):
    make_token(user)
    with app.app_context():
        db.session.add(ApiToken(user_id=owner_id(), name="dup", token_hash="0" * 64, prefix="st_dup",
                                scopes="renewals:read", slot=1, expires_at=utcnow() + timedelta(days=1)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
    # A request that saw an old list of slots loses at the database and takes the next one.
    real = api_tokens.used_slots
    seen = {"calls": 0}

    def stale_once(uid):
        seen["calls"] += 1
        return set() if seen["calls"] == 1 else real(uid)

    monkeypatch.setattr(api_tokens, "used_slots", stale_once)
    assert make_token(user, name="Raced")[1]
    with app.app_context():
        assert sorted(t.slot for t in ApiToken.query) == [1, 2]
    # If it always sees an empty list, it still can't make a sixth.
    for n in range(3):
        make_token(user, name=f"Fill {n}")
    monkeypatch.setattr(api_tokens, "used_slots", lambda uid: set())
    assert make_token(user, name="Sixth")[0].status_code == 409
    with app.app_context():
        assert ApiToken.query.filter(ApiToken.slot.isnot(None)).count() == 5


def test_parallel_creates_never_make_a_sixth(user, app):
    with app.app_context():
        uid = owner_id()
    results = []

    def create_one(n):
        with app.app_context():
            token, _ = api_tokens.create(db.session.get(User, uid), f"Thread {n}", 30, ["renewals:read"])
            results.append(token is not None)
            db.session.remove()

    threads = [threading.Thread(target=create_one, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    with app.app_context():
        active = ApiToken.query.filter(ApiToken.slot.isnot(None)).all()
        assert len(active) == 5 and sorted(t.slot for t in active) == [1, 2, 3, 4, 5]
    assert results.count(True) == 5


def test_password_reset_disconnects_every_extension(user, app):
    _, secret = make_token(user)
    with app.app_context():
        raw = tokens.issue(User.query.one(), "reset_password", 30)
    user.post(f"/reset-password/{raw}", data={"password": "NewPassword456!", "confirm": "NewPassword456!"})
    assert call(app.test_client(), "/api/v1/me", secret).get_json() == {"error": "revoked"}
    with app.app_context():
        assert ApiToken.query.one().slot is None


# ---------- limits, last used, CORS, logs ----------

def test_contract_limits():
    assert (api.requests_per_token.limit, api.requests_per_token.window) == (120, 3600)
    assert (api.failed_checks_per_ip.limit, api.failed_checks_per_ip.window) == (20, 600)
    assert api_tokens.MAX_ACTIVE == 5 and api_tokens.DEFAULT_DAYS == 90 and api_tokens.MAX_DAYS == 365


def test_too_many_requests_say_when_to_retry(user, app, monkeypatch):
    _, secret = make_token(user)
    client = app.test_client()
    monkeypatch.setattr(api, "requests_per_token", RateLimiter(2, 3600))
    assert [call(client, "/api/v1/me", secret).status_code for _ in range(2)] == [200, 200]
    slow = call(client, "/api/v1/me", secret)
    assert slow.status_code == 429 and slow.get_json() == {"error": "slow-down"}
    assert 0 < int(slow.headers["Retry-After"]) <= 3600
    monkeypatch.setattr(api, "failed_checks_per_ip", RateLimiter(3, 600))
    for _ in range(3):
        assert call(client, "/api/v1/me", "st_" + "x" * 43).status_code == 401
    blocked = call(client, "/api/v1/me", secret)  # even a good token waits now
    assert blocked.status_code == 429 and 0 < int(blocked.headers["Retry-After"]) <= 600


def test_last_used_is_written_at_most_once_a_minute(user, app, monkeypatch):
    _, secret = make_token(user)
    client = app.test_client()
    start = utcnow().replace(microsecond=0)

    def last_used_after(moment):
        monkeypatch.setattr(api, "utcnow", lambda: moment)
        call(client, "/api/v1/me", secret)
        with app.app_context():
            return ApiToken.query.one().last_used_at

    assert last_used_after(start) == start
    assert last_used_after(start + timedelta(seconds=30)) == start  # no write within the minute
    assert last_used_after(start + timedelta(seconds=61)) == start + timedelta(seconds=61)


def test_cors_allows_only_the_configured_extension(user, app, monkeypatch):
    _, secret = make_token(user)
    client = app.test_client()
    preflight = {"Origin": ORIGIN, "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "authorization"}
    monkeypatch.delenv("EXTENSION_ORIGIN", raising=False)
    assert "Access-Control-Allow-Origin" not in client.options("/api/v1/renewals", headers=preflight).headers
    monkeypatch.setenv("EXTENSION_ORIGIN", ORIGIN)
    answer = client.options("/api/v1/renewals", headers=preflight)  # no token needed to ask
    assert answer.status_code == 200 and answer.headers["Access-Control-Allow-Origin"] == ORIGIN
    assert answer.headers["Access-Control-Allow-Headers"] == "Authorization"
    assert answer.headers["Access-Control-Allow-Methods"] == "GET"
    assert "Access-Control-Allow-Credentials" not in answer.headers
    real = call(client, "/api/v1/renewals", secret, headers={"Origin": ORIGIN})
    assert real.headers["Access-Control-Allow-Origin"] == ORIGIN and "Origin" in real.headers["Vary"]
    for other in ("https://evil.example", "chrome-extension://" + "b" * 32):
        assert "Access-Control-Allow-Origin" not in call(client, "/api/v1/renewals", secret,
                                                         headers={"Origin": other}).headers
    for bad_setting in ("*", ORIGIN + "/", "chrome-extension://*"):  # never a wildcard or a sloppy value
        monkeypatch.setenv("EXTENSION_ORIGIN", bad_setting)
        assert "Access-Control-Allow-Origin" not in client.options("/api/v1/renewals", headers=preflight).headers


def test_secret_never_reaches_the_logs(user, app, caplog):
    caplog.set_level(logging.DEBUG)
    _, secret = make_token(user)
    call(app.test_client(), "/api/v1/renewals", secret)
    with app.app_context():
        token_id = ApiToken.query.one().id
    user.post(f"/settings/tokens/{token_id}/revoke")
    call(app.test_client(), "/api/v1/renewals", secret)
    assert secret not in caplog.text


def test_schema_check_knows_the_table(app):
    from app.schema import EXPECTED_TABLES, schema_issues

    assert "api_tokens" in EXPECTED_TABLES
    with app.app_context():
        assert schema_issues(db.engine) == []
