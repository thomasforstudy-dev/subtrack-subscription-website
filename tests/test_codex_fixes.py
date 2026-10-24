"""Fixes for Codex's 24 Oct reviews (docs/SECURITY/2026-10-24-review.md and the two QA reports)."""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app import db
from app.dashboard import activity
from app.forecast import forecast
from app.models import Bill, Subscription, User
from app.roulette import food_places
from app.schedule import local_now
from app.security import RateLimiter


# ---------- S2 / S3: private pages are never cached; basic browser protections ----------

def test_private_pages_are_not_cached_and_have_security_headers(user):
    for path in ("/dashboard", "/subscriptions/", "/bills/", "/links/", "/settings", "/settings.json", "/dashboard.json"):
        res = user.get(path, follow_redirects=True)
        assert "no-store" in res.headers.get("Cache-Control", ""), path
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
        assert res.headers["Referrer-Policy"]


def test_public_pages_get_the_headers_but_can_be_cached(app):
    res = app.test_client().get("/")
    assert res.headers["X-Frame-Options"] == "DENY" and "no-store" not in res.headers.get("Cache-Control", "")


def test_stricter_route_headers_are_kept(user):
    # The calendar sets its own Referrer-Policy: the general one must not replace it.
    res = user.get("/calendar/")
    assert res.headers["Referrer-Policy"] == "no-referrer"


# ---------- S4: the limiter remembers at most MAX_KEYS keys ----------

def test_rate_limiter_has_a_hard_key_cap():
    limiter = RateLimiter(5, 3600)
    limiter.MAX_KEYS = 50
    for n in range(500):  # 500 different "IPs", all still inside their window
        assert limiter.hit(f"ip-{n}")
    assert len(limiter._hits) <= 50
    # Limits still work for a key that keeps hitting.
    for _ in range(4):
        limiter.hit("busy")
    assert limiter.hit("busy") and not limiter.hit("busy")


# ---------- QA-02: activity dates are in the user's time zone ----------

def test_new_plan_activity_uses_the_local_date(app, user):
    with app.app_context():
        me = User.query.one()
        me.timezone = "Asia/Ho_Chi_Minh"
        # 19:29 UTC on 23 Oct is 02:29 on 24 Oct in Vietnam.
        sub = Subscription(user_id=me.id, name="Night plan", amount=Decimal(1), currency="USD", cycle="monthly",
                           next_renewal_at=datetime(2026, 11, 24).date(), created_at=datetime(2026, 10, 23, 19, 29))
        db.session.add(sub)
        db.session.commit()
        with app.test_request_context():
            rows = [r for r in activity(me, local_now(me.timezone).date()) if r["title"] == "Night plan"]
    assert rows[0]["when"].isoformat() == "2026-10-24"


# ---------- QA-03 / G04: never average VND and USD together ----------

def add(email, merchant, total, currency, day, category="food"):
    me = User.query.filter_by(email=email).one()
    db.session.add(Bill(user_id=me.id, merchant=merchant, total=Decimal(total), currency=currency,
                        transaction_date=day, category=category, kind="receipt"))
    db.session.commit()
    return me


def test_roulette_average_stays_in_one_currency(app, user):
    with app.app_context():
        me = User.query.one()
        today = local_now(me.timezone).date()
        add(me.email, "Cafe QA", "60000", "VND", today - timedelta(days=1))
        add(me.email, "Cafe QA", "70000", "VND", today - timedelta(days=2))
        add(me.email, "Cafe QA", "4", "USD", today - timedelta(days=3))
        add(me.email, "Other place", "50000", "VND", today - timedelta(days=4))
        place = next(p for p in food_places(me) if p["name"] == "Cafe QA")
    assert place["currency"] == "VND" and place["average"] == Decimal("65000.00")  # (60000 + 70000) / 2


def test_forecast_typical_amount_stays_in_one_currency(app, user):
    with app.app_context():
        me = User.query.one()
        today = local_now(me.timezone).date()
        monday = today - timedelta(days=today.weekday()) - timedelta(weeks=1)
        add(me.email, "Cafe QA", "100000", "VND", monday)
        add(me.email, "Cafe QA", "90000", "VND", monday - timedelta(weeks=1))
        add(me.email, "Cafe QA", "5", "USD", monday - timedelta(weeks=2))
        shop = next(s for s in forecast(me, "week")["shops"] if s["name"] == "Cafe QA")
    assert shop["currency"] == "VND" and shop["typical"] == Decimal("95000.00")  # not (100000 + 90000 + 5) / 3


# ---------- G08 / G09: the reading pages and Subby speak Vietnamese ----------

def test_static_files_have_no_hidden_control_characters():
    # A stray backspace (from a mangled "\b") once broke the "?tour=1" check in tour.js.
    static = Path(__file__).resolve().parent.parent / "app" / "static"
    for path in list(static.glob("*.js")) + list(static.glob("*.css")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text), path.name
    assert r"/[?&]tour=1\b/" in (static / "tour.js").read_text(encoding="utf-8")


def test_subby_voice_controls_are_translated(app):
    client = app.test_client()
    client.set_cookie("ui_lang", "vi")
    page = client.get("/").get_data(as_text=True)
    assert "🎙️ Giọng nói" in page and "Kết thúc Voice" not in page
