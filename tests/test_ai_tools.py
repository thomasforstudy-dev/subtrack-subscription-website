"""AI tools: spending forecast, Read aloud and the food roulette."""

import base64
import io
import wave
from datetime import timedelta
from decimal import Decimal

import pytest

from app import db
from app.ai_providers import FakeProvider, ProviderUnavailable, gemini_audio
from app.forecast import forecast
from app.models import Bill, BillLine, User
from app.read_aloud import MAX_CHUNK, split_paragraphs
from app.roulette import food_places
from app.schedule import local_now

from .conftest import sign_up
from .test_bill_jobs import docx


def add_bill(email, merchant, total, day, category="other", currency="VND", lines=(), kind="receipt"):
    user = User.query.filter_by(email=email).one()
    bill = Bill(user_id=user.id, merchant=merchant, total=Decimal(total), currency=currency,
                transaction_date=day, category=category, kind=kind)
    db.session.add(bill)
    db.session.flush()
    for n, text in enumerate(lines, start=1):
        db.session.add(BillLine(bill_id=bill.id, position=n, description=text))
    db.session.commit()
    return user


def last_weeks_mondays(user, count):
    today = local_now(user.timezone).date()
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=k) for k in range(1, count + 1)]


# ---------- forecast ----------------------------------------------------------

def test_week_forecast_counts_how_often_each_shop_appears(app, user):
    with app.app_context():
        me = User.query.one()
        weeks = last_weeks_mondays(me, 4)
        for n, monday in enumerate(weeks):
            add_bill(me.email, "Highlands Coffee", "50000", monday + timedelta(days=2), lines=["Cà phê sữa"])
            if n % 2 == 0:
                add_bill(me.email, "Phở 24", "80000", monday + timedelta(days=4))
        result = forecast(me, "week")
    assert result["counted"] == 4  # judged on the 4 weeks since the first bill, not 12
    shops = {s["name"]: s for s in result["shops"]}
    assert shops["Highlands Coffee"]["chance"] == 100 and shops["Highlands Coffee"]["typical"] == Decimal("50000.00")
    assert shops["Phở 24"]["chance"] == 50
    assert result["things"] == [{"name": "Cà phê sữa", "chance": 100}]
    # (4 x 50,000 + 2 x 80,000) / 4 weeks
    assert result["expected"] == [{"currency": "VND", "amount": Decimal("90000.00")}]


def test_day_forecast_only_learns_from_the_same_weekday(app, user):
    with app.app_context():
        me = User.query.one()
        tomorrow = local_now(me.timezone).date() + timedelta(days=1)
        for k in (1, 2, 3):
            add_bill(me.email, "Bánh mì", "25000", tomorrow - timedelta(weeks=k))
            add_bill(me.email, "Other day shop", "99000", tomorrow - timedelta(weeks=k, days=1))
        result = forecast(me, "day")
    assert [s["name"] for s in result["shops"]] == ["Bánh mì"]
    assert result["shops"][0]["chance"] == 100 and result["target"] == tomorrow


def test_forecast_ignores_other_users_card_bills_and_archived_bills(app, user):
    sign_up(app.test_client(), "other@example.com")
    with app.app_context():
        me = User.query.filter(User.email != "other@example.com").one()
        monday = last_weeks_mondays(me, 1)[0]
        add_bill("other@example.com", "Their shop", "10", monday)
        add_bill(me.email, "Card statement", "10", monday, kind="card_bill")
        archived = Bill(user_id=me.id, merchant="Old", total=Decimal(5), currency="VND",
                        transaction_date=monday, status="archived")
        db.session.add(archived)
        db.session.commit()
        result = forecast(me, "week")
    assert result["shops"] == [] and result["counted"] == 0


def test_forecast_page_and_ask_gemini_sends_only_the_numbers(app, user, monkeypatch):
    fake = FakeProvider("[fake model] You'll probably get coffee.")
    monkeypatch.setattr("app.forecast.chat_provider", lambda: fake)
    with app.app_context():
        me = User.query.one()
        for monday in last_weeks_mondays(me, 3):
            add_bill(me.email, "Highlands Coffee", "50000", monday)
        db.session.add(Bill(user_id=me.id, merchant="Highlands Coffee", total=Decimal(1), currency="VND",
                            transaction_date=monday, notes="secret note"))
        db.session.commit()
    page = user.get("/tools/forecast/?period=week").get_data(as_text=True)
    assert "Highlands Coffee" in page and "100%" in page
    page = user.post("/tools/forecast/", data={"period": "week"}).get_data(as_text=True)
    assert "You&#39;ll probably get coffee." in page
    sent = fake.calls[0]
    assert "Highlands Coffee: 100% chance" in sent["question"] and "secret note" not in sent["question"]
    assert "English" in sent["system"]


def test_forecast_empty_state_and_bad_period(app, user):
    page = user.get("/tools/forecast/?period=year").get_data(as_text=True)
    assert "No receipts to learn from yet" in page and 'aria-current="page">Next week' in page


def test_ai_tools_need_login(client):
    for path in ("/tools/", "/tools/forecast/", "/tools/read-aloud/", "/tools/food-roulette/"):
        assert client.get(path).status_code == 302


# ---------- read aloud --------------------------------------------------------

def test_upload_word_file_shows_its_paragraphs(user):
    data = {"document": (io.BytesIO(docx(["Chương 1", "Ngày xưa có một chú mèo."])), "story.docx")}
    page = user.post("/tools/read-aloud/", data=data, content_type="multipart/form-data").get_data(as_text=True)
    assert 'data-reader-part="0" tabindex="0">Chương 1</p>' in page
    assert "Ngày xưa có một chú mèo." in page and "story.docx" in page and "read-aloud.js" in page


def test_pasted_text_and_wrong_files(user):
    page = user.post("/tools/read-aloud/", data={"text": "First.\n\nSecond."}).get_data(as_text=True)
    assert 'data-reader-part="1"' in page and "Second." in page
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    page = user.post("/tools/read-aloud/", data={"document": (io.BytesIO(png), "cat.png")},
                     content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "data-reader-part" not in page


def test_long_paragraphs_are_cut_at_sentence_ends():
    text = ("This is one sentence. " * 200).strip()
    parts = split_paragraphs(text)
    assert len(parts) > 1 and all(len(p) <= MAX_CHUNK for p in parts)
    assert all(p.endswith(".") for p in parts)
    assert " ".join(parts) == text


def test_speak_returns_wav_from_gemini(user, monkeypatch):
    asked = {}

    def fake_speak(text, voice):
        asked.update(text=text, voice=voice)
        return b"RIFF....WAVE"

    monkeypatch.setattr("app.read_aloud.gemini_speak", fake_speak)
    token = user.csrf_token()
    res = user.post("/tools/read-aloud/speak", json={"text": "  Xin   chào ", "voice": "Hacker"},
                    headers={"X-CSRF-Token": token})
    assert res.status_code == 200 and res.mimetype == "audio/wav" and res.data == b"RIFF....WAVE"
    assert asked == {"text": "Xin chào", "voice": "Kore"}  # unknown voice -> the default
    # Without the CSRF header another website could spend our quota.
    assert user.post("/tools/read-aloud/speak", json={"text": "hi"}, csrf=False).status_code == 400


def test_speak_tells_the_page_when_gemini_is_busy(user, monkeypatch):
    def busy(text, voice):
        raise ProviderUnavailable("busy")

    monkeypatch.setattr("app.read_aloud.gemini_speak", busy)
    res = user.post("/tools/read-aloud/speak", json={"text": "hi"}, headers={"X-CSRF-Token": user.csrf_token()})
    assert res.status_code == 503 and res.get_json() == {"error": "voice-unavailable"}


def test_gemini_audio_wraps_raw_samples_in_a_wav_header():
    samples = b"\x00\x01" * 2400
    reply = {"candidates": [{"content": {"parts": [{"inlineData": {
        "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(samples).decode()}}]}}]}
    with wave.open(io.BytesIO(gemini_audio(reply))) as wav:
        assert wav.getframerate() == 24000 and wav.getnframes() == 2400
    ready = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(b"RIFF").decode()}}]}}]}
    assert gemini_audio(ready) == b"RIFF"
    for bad in ({}, {"candidates": [{"content": {"parts": [{"text": "no audio"}]}}]}, None):
        with pytest.raises(ProviderUnavailable):
            gemini_audio(bad)


# ---------- food roulette -----------------------------------------------------

def test_roulette_uses_only_my_food_receipts(app, user):
    sign_up(app.test_client(), "other@example.com")
    with app.app_context():
        me = User.query.filter(User.email != "other@example.com").one()
        today = local_now(me.timezone).date()
        for days in (1, 8, 15):
            add_bill(me.email, "Phở Thìn", "60000", today - timedelta(days=days), category="food")
        add_bill(me.email, "phở thìn ", "60000", today - timedelta(days=20), category="food")  # same place
        add_bill(me.email, "Cơm Tấm Cali", "45000", today - timedelta(days=40), category="food")
        add_bill(me.email, "Shopee", "300000", today, category="shopping")
        add_bill("other@example.com", "Their restaurant", "1", today, category="food")
        places = {p["name"]: p for p in food_places(me)}
    assert set(places) == {"Phở Thìn", "Cơm Tấm Cali"}
    assert places["Phở Thìn"]["visits"] == 4 and places["Phở Thìn"]["days_ago"] == 1
    assert places["Phở Thìn"]["average"] == Decimal("60000.00")
    # "Something different" favours the place not visited for 40 days.
    assert places["Cơm Tấm Cali"]["different"] > places["Phở Thìn"]["different"]
    page = user.get("/tools/food-roulette/").get_data(as_text=True)
    assert "roulette.js" in page and "Their restaurant" not in page and "Cơm Tấm Cali" in page


def test_roulette_empty_state(user):
    page = user.get("/tools/food-roulette/").get_data(as_text=True)
    assert "You need at least 2 places to eat" in page and "roulette.js" not in page


def test_tools_page_links_all_three(user):
    page = user.get("/tools/").get_data(as_text=True)
    for path in ("/tools/forecast/", "/tools/read-aloud/", "/tools/food-roulette/"):
        assert f'href="{path}"' in page
