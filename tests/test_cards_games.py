"""Fix_Thing_2: the card holder, the three games, brand logos, the Bills page
month view and the menu pill."""

from datetime import timedelta
from decimal import Decimal

from app import db
from app.brands import brand
from app.cards import MAX_CARDS, masked_number, network_for
from app.models import Bill, Card, User
from app.schedule import local_now
from tests.conftest import CSRFClient, sign_up


def me():
    return User.query.filter_by(email="a@example.com").one()


# ---------- card holder ----------

def test_add_card_keeps_only_first6_and_last4(app, user):
    res = user.post("/cards/", data={"name": "Techcombank Visa", "first6": "411111", "last4": "1234",
                                     "kind": "debit", "color": "ink"}, follow_redirects=True)
    assert res.status_code == 200
    with app.app_context():
        card = Card.query.one()
        assert (card.first6, card.last4, card.kind, card.color) == ("411111", "1234", "debit", "ink")
        assert not hasattr(card, "number") and not hasattr(card, "cvv")
    page = res.get_data(as_text=True)
    assert "4111 11•• •••• 1234" in page and "VISA" in page


def test_card_form_refuses_bad_digits_and_odd_values(app, user):
    for first6, last4 in (("47809", "1234"), ("4111111", "1234"), ("411111", "26a9"), ("", "")):
        user.post("/cards/", data={"first6": first6, "last4": last4})
    user.post("/cards/", data={"first6": "411111", "last4": "1234", "kind": "gold", "color": "url(x)"})
    with app.app_context():
        cards = Card.query.all()
        assert len(cards) == 1  # only the last one was valid
        assert cards[0].kind == "credit" and cards[0].color == "violet"  # unknown values fall back


def test_card_holder_has_a_limit(app, user):
    for n in range(MAX_CARDS + 2):
        user.post("/cards/", data={"first6": "411111", "last4": f"{n:04d}"})
    with app.app_context():
        assert Card.query.filter_by(removed_at=None).count() == MAX_CARDS


def test_cards_are_private_and_removal_keeps_the_row(app, user):
    user.post("/cards/", data={"name": "Mine", "first6": "512345", "last4": "1111"})
    with app.app_context():
        card_id = Card.query.one().id

    app.test_client_class = CSRFClient
    other = app.test_client()
    sign_up(other, "b@example.com")
    page = other.get("/bills/").get_data(as_text=True)
    assert "Mine" not in page and "1111" not in page
    assert other.post(f"/cards/{card_id}/remove").status_code == 404

    user.post(f"/cards/{card_id}/remove")
    with app.app_context():
        card = db.session.get(Card, card_id)
        assert card is not None and card.removed_at is not None  # hidden, not deleted
    assert "Mine" not in user.get("/bills/").get_data(as_text=True)


def test_network_and_masking():
    assert network_for("411111") == "visa"
    assert network_for("512345") == "mastercard" and network_for("222100") == "mastercard"
    assert network_for("970407") == "napas"
    assert network_for("371234") == "amex" and network_for("353012") == "jcb"
    assert masked_number(Card(first6="411111", last4="1234")) == "4111 11•• •••• 1234"


def test_card_shows_this_months_spending(app, user):
    user.post("/cards/", data={"name": "Daily card", "first6": "411111", "last4": "1234"})
    with app.app_context():
        owner = me()
        today = local_now(owner.timezone).date()
        db.session.add_all([
            Bill(user_id=owner.id, merchant="GS25", total=Decimal("14000"), currency="VND", kind="receipt",
                 category="food", card_last4="1234", transaction_date=today),
            Bill(user_id=owner.id, merchant="Old", total=Decimal("99000"), currency="VND", kind="receipt",
                 category="food", card_last4="1234", transaction_date=today.replace(day=1) - timedelta(days=1)),
        ])
        db.session.commit()
    page = user.get("/bills/").get_data(as_text=True)
    assert "This month: 14,000 VND" in page


# ---------- Bills page: spent this month by category ----------

def test_month_spend_by_category(app, user):
    with app.app_context():
        owner = me()
        today = local_now(owner.timezone).date()
        for merchant, total, category in (("Phuc Long", "175000", "food"), ("Decathlon", "139000", "shopping"),
                                          ("GS25", "14000", "food")):
            db.session.add(Bill(user_id=owner.id, merchant=merchant, total=Decimal(total), currency="VND",
                                kind="receipt", category=category, transaction_date=today))
        db.session.add(Bill(user_id=owner.id, merchant="Claude", total=Decimal("22.22"), currency="USD",
                            kind="receipt", category="software", transaction_date=today))
        db.session.commit()
    page = user.get("/bills/").get_data(as_text=True)
    assert "Spent this month" in page
    assert "328,000" in page  # VND only: 175,000 + 139,000 + 14,000
    assert "+ 22.22 USD" in page  # the other currency is listed apart, never added


# ---------- games ----------

def test_game_pages_load_and_are_linked(user):
    tools = user.get("/tools/").get_data(as_text=True)
    for path, words in (("/tools/coin-flip", "coin-flip.js"), ("/tools/blackjack", "blackjack.js"),
                        ("/tools/case-spin", "case-spin.js")):
        assert path in tools
        res = user.get(path)
        assert res.status_code == 200 and words in res.get_data(as_text=True)


def test_games_need_login(app):
    client = app.test_client()
    for path in ("/tools/coin-flip", "/tools/blackjack", "/tools/case-spin"):
        assert client.get(path).status_code == 302


# ---------- brand logos ----------

def test_brand_logos_for_known_services(user):
    assert brand("Netflix Premium")["slug"] == "netflix"
    assert brand("ChatGPT Plus")["slug"] == "openai"
    assert brand("Google AI Pro (5 TB)")["slug"] == "google"
    assert brand("Bún bò Huế") is None
    page = user.get("/subscriptions/new").get_data(as_text=True)
    assert "/static/brands/netflix.svg" in page and "/static/brands/spotify.svg" in page


# ---------- menu pill ----------

def test_menu_has_the_gliding_pill(user):
    page = user.get("/dashboard").get_data(as_text=True)
    assert "data-nav-current" in page


# ---------- dashboard: archived plans stop asking "were you charged?" ----------

def test_archived_plan_renewals_stop_asking(app, user):
    from app.dashboard import activity, summary
    from app.models import Renewal, Subscription
    with app.app_context():
        owner = me()
        today = local_now(owner.timezone).date()
        gone = Subscription(user_id=owner.id, name="Old gym", amount=Decimal("1500000"), currency="VND",
                            cycle="monthly", next_renewal_at=today + timedelta(days=20), status="archived")
        kept = Subscription(user_id=owner.id, name="Music", amount=Decimal("59000"), currency="VND",
                            cycle="monthly", next_renewal_at=today + timedelta(days=20), status="active")
        db.session.add_all([gone, kept])
        db.session.flush()
        db.session.add_all([
            Renewal(subscription_id=gone.id, user_id=owner.id, due_date=today - timedelta(days=3),
                    amount=gone.amount, currency="VND", status="expected"),
            Renewal(subscription_id=gone.id, user_id=owner.id, due_date=today - timedelta(days=33),
                    amount=gone.amount, currency="VND", status="paid"),
            Renewal(subscription_id=kept.id, user_id=owner.id, due_date=today - timedelta(days=2),
                    amount=kept.amount, currency="VND", status="expected"),
        ])
        db.session.commit()
        rows = [(r.subscription_id, r.status) for r in summary(owner)["expected"]]
        assert (gone.id, "expected") not in rows
        assert (gone.id, "paid") in rows and (kept.id, "expected") in rows
        with app.test_request_context():
            titles = [(i["title"], i["status"]) for i in activity(owner, today) if i["kind"] == "renewal"]
        assert ("Old gym", "expected") not in titles and ("Music", "expected") in titles
