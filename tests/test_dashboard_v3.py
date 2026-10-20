"""Dashboard v3 (AllOutFree): real numbers only, one currency at a time, own data only."""

from datetime import date, timedelta
from decimal import Decimal

from app import db
from app.dashboard import main_currency, money_text, month_start, overview
from app.models import Bill, Renewal, Subscription, User
from app.schedule import local_now

from .conftest import sign_up


def add_plan(client, name, amount, currency, days):
    today = local_now("UTC").date()
    client.post("/subscriptions/new", data={"name": name, "amount": amount, "currency": currency, "cycle": "monthly",
                                            "next_renewal_at": (today + timedelta(days=days)).isoformat(), "lead_days": "7"})


def test_money_format_matches_the_currency():
    assert money_text(Decimal("398000"), "VND") == "398,000"
    assert money_text(Decimal("20"), "USD") == "20.00"
    assert money_text(None, "USD") == "—"


def test_month_start_crosses_years():
    assert month_start(date(2026, 1, 15), -1) == date(2025, 12, 1)
    assert month_start(date(2026, 11, 30), 2) == date(2027, 1, 1)


def test_main_currency_is_the_one_most_plans_use(user, app):
    add_plan(user, "Netflix", "260000", "VND", 3)
    add_plan(user, "Spotify", "59000", "VND", 5)
    add_plan(user, "ChatGPT", "20.00", "USD", 9)
    with app.test_request_context():  # overview() builds page links
        owner = User.query.one()
        data = overview(owner)
        assert main_currency(Subscription.query.all()) == "VND"
        assert data["main_total"]["monthly"] == Decimal("319000.00")
        assert [row["currency"] for row in data["other_totals"]] == ["USD"]  # never added to VND
        assert len(data["week"]) == 2 and data["week_total"] == Decimal("319000")
        assert data["active_count"] == 3


def test_chart_uses_history_projections_and_receipts(user, app):
    add_plan(user, "Netflix", "260000", "VND", 3)
    with app.test_request_context():
        owner = User.query.one()
        today = local_now(owner.timezone).date()
        sub = Subscription.query.one()
        last_month = month_start(today, -1)
        db.session.add(Renewal(subscription_id=sub.id, user_id=owner.id, due_date=last_month, amount=Decimal("260000"),
                               currency="VND", status="paid"))
        db.session.add(Renewal(subscription_id=sub.id, user_id=owner.id, due_date=month_start(today, -2),
                               amount=Decimal("260000"), currency="VND", status="skipped"))  # not charged: not counted
        db.session.add(Bill(user_id=owner.id, kind="receipt", merchant="Shop", currency="VND", total=Decimal("99000"),
                            transaction_date=last_month, status="confirmed"))
        db.session.add(Bill(user_id=owner.id, kind="receipt", merchant="Elsewhere", currency="USD", total=Decimal("5"),
                            transaction_date=last_month, status="confirmed"))  # another currency: not in the VND chart
        db.session.commit()
        bars = {bar["month"]: bar for bar in overview(owner)["bars"]}
    assert len(bars) == 6
    assert bars[last_month]["renewals"] == Decimal("260000") and bars[last_month]["spent"] == Decimal("99000")
    assert bars[month_start(today, -2)]["renewals"] == 0
    renewal_month = month_start(today + timedelta(days=3))
    assert bars[renewal_month]["renewals"] >= Decimal("260000")  # the coming renewal, from the plan's schedule
    assert max(bar["renewals_pct"] for bar in bars.values()) == 100


def test_dashboard_page_shows_only_my_own_activity(client, app):
    sign_up(client, "other@example.com")
    add_plan(client, "Their secret plan", "9.99", "USD", 4)
    client.post("/logout")
    sign_up(client, "me@example.com")
    add_plan(client, "My plan", "50000", "VND", 2)
    page = client.get("/dashboard").get_data(as_text=True)
    assert "My plan" in page and "Their secret plan" not in page
    assert 'data-count="50000.00"' in page  # count-up target = the real monthly total
    assert "50,000" in page  # and the number is on the page without JavaScript


def test_greeting_follows_the_users_time_zone(user, app, monkeypatch):
    from app import dashboard

    with app.test_request_context():
        owner = User.query.one()
        real = dashboard.local_now
        monkeypatch.setattr(dashboard, "local_now", lambda zone, now=None: real(zone).replace(hour=20))
        assert overview(owner)["greeting"] == "evening"


def test_empty_dashboard_is_friendly(user):
    page = user.get("/dashboard").get_data(as_text=True)
    assert "Chưa có gói nào đang dùng" in page and "Thêm một gói để thấy biểu đồ" in page
