"""Regressions for the independent runtime review of 19 Oct 2026 (RUNTIME-1, 4, 5, 6).

Each test goes through the real endpoint (login + CSRF), because the bugs
only showed up at request level. Nothing here contacts a model or a website.
"""

from datetime import date
from decimal import Decimal

import pytest
import requests

from app import ai_providers, db
from app.links import fill_missing_fingerprints, url_fingerprint
from app.models import Link, Subscription
from tests.conftest import sign_up

BAD_URLS = [
    "https://example.test:abc/path",   # port isn't a number
    "https://example.test:99999/path",  # port too big
    "https://[invalid/path",            # half-written IPv6 address
    "https://exa mple.test/",           # space inside
    "https://:443/",                    # no host at all
]


@pytest.fixture()
def no_lookup(monkeypatch):
    monkeypatch.setattr("app.links.fetch_preview", lambda url: {})


# ---------- RUNTIME-4: broken links give a normal error, never a 500 ---------

@pytest.mark.parametrize("bad", BAD_URLS)
def test_bad_link_on_create_is_a_friendly_error(user, app, no_lookup, bad):
    res = user.post("/links/new", data={"url": bad, "title": "Synthetic"})
    assert res.status_code == 200
    assert "flash" in res.get_data(as_text=True)
    with app.app_context():
        assert Link.query.count() == 0


@pytest.mark.parametrize("bad", BAD_URLS)
def test_bad_link_on_edit_keeps_the_saved_row(user, app, no_lookup, bad):
    user.post("/links/new", data={"url": "https://example.test/ok", "title": "Good"})
    with app.app_context():
        link_id = Link.query.one().id
    res = user.post(f"/links/{link_id}/edit", data={"url": bad, "title": "Changed"})
    assert res.status_code == 200
    with app.app_context():
        link = Link.query.one()
        assert link.url == "https://example.test/ok" and link.title == "Good"


@pytest.mark.parametrize("bad", BAD_URLS)
def test_bad_link_preview_returns_empty_json(user, bad):
    res = user.post("/links/preview", data={"url": bad})
    assert res.status_code == 200 and res.get_json() == {}


@pytest.mark.parametrize("bad", BAD_URLS)
def test_bad_manage_url_on_a_subscription(user, app, bad):
    res = user.post("/subscriptions/new", data={
        "name": "Plan", "amount": "1", "currency": "USD", "cycle": "monthly",
        "next_renewal_at": "2026-11-01", "manage_url": bad,
    })
    assert "Manage link" in res.get_data(as_text=True)
    with app.app_context():
        assert Subscription.query.count() == 0


def test_old_broken_rows_dont_break_start_up_or_the_list(user, app):
    # Saved before links were checked: written straight into the database.
    with app.app_context():
        from app.models import User

        owner = User.query.one()
        for bad in BAD_URLS[:3]:
            db.session.add(Link(user_id=owner.id, url=bad, title=f"Old {bad}"))
        db.session.commit()
        assert fill_missing_fingerprints() == 3
        assert all(len(link.url_hash) == 64 for link in Link.query)
    assert user.get("/links/").status_code == 200
    assert url_fingerprint("https://[invalid/path") == url_fingerprint("https://[INVALID/path")


# ---------- RUNTIME-5: pin never redirects to another website ---------------

def pinned_link(user, app):
    user.post("/links/new", data={"url": "https://example.test/review", "title": "Synthetic link"})
    with app.app_context():
        return Link.query.one().id


def test_pin_ignores_an_external_referer(user, app, no_lookup):
    link_id = pinned_link(user, app)
    res = user.post(f"/links/{link_id}/pin", headers={"Referer": "https://external.example.test/redirect"})
    assert res.status_code == 302
    assert res.headers["Location"] == "/links/"
    with app.app_context():
        assert Link.query.one().is_pinned  # the pin itself still worked


def test_pin_returns_to_the_same_filtered_list(user, app, no_lookup):
    link_id = pinned_link(user, app)
    res = user.post(f"/links/{link_id}/pin", headers={"Referer": "http://localhost/links/?q=review"})
    assert res.headers["Location"] == "/links/?q=review"


@pytest.mark.parametrize("target", ["https://evil.example/", "//evil.example/links/", "/admin/users"])
def test_pin_next_field_only_allows_the_links_page(user, app, no_lookup, target):
    link_id = pinned_link(user, app)
    res = user.post(f"/links/{link_id}/pin", data={"next": target})
    assert res.headers["Location"] == "/links/"


# ---------- RUNTIME-6: odd model replies and bad settings -> JSON errors ------

class Reply:
    def __init__(self, data, status=200, bad_json=False):
        self.data, self.status_code, self.ok, self.bad_json = data, status, status < 400, bad_json

    def json(self):
        if self.bad_json:
            raise ValueError("not JSON")
        return self.data


@pytest.fixture()
def models_env(monkeypatch):
    for name in ["SUBBY_FALLBACK", "GEMINI_MODEL"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PHI_BASE_URL", "http://model.invalid")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-unused-key")


def ask_with(client, monkeypatch, provider, reply):
    monkeypatch.setenv("SUBBY_PROVIDER", provider)
    monkeypatch.setattr(ai_providers.requests, "post", lambda *a, **k: reply)
    return client.post("/subby/ask", json={"question": "Synthetic test"})


@pytest.mark.parametrize(
    "reply",
    [
        Reply({"choices": None}),
        Reply({"choices": []}),
        Reply({"choices": [None]}),
        Reply({"choices": [{"message": None}]}),
        Reply({"choices": [{"message": {"content": 42}}]}),
        Reply(["not", "a", "dict"]),
        Reply(None, bad_json=True),
    ],
)
def test_malformed_phi_reply_is_a_json_error(client, monkeypatch, models_env, reply):
    res = ask_with(client, monkeypatch, "phi", reply)
    assert res.status_code == 502
    assert res.get_json() == {"answer": None, "reason": "model-failed", "provider": "phi"}


@pytest.mark.parametrize(
    "reply",
    [
        Reply({"candidates": [{"content": {"parts": None}}]}),
        Reply({"candidates": None}),
        Reply({"candidates": "x"}),
        Reply({"candidates": [{"finishReason": "SAFETY"}]}),  # blocked: no content
        Reply({"candidates": [{"content": {"parts": [{"text": None}]}}]}),
        Reply({"candidates": [{"content": {"parts": ["just text"]}}]}),
        Reply(None, bad_json=True),
    ],
)
def test_malformed_gemini_reply_is_a_json_error(client, monkeypatch, models_env, reply):
    res = ask_with(client, monkeypatch, "gemini", reply)
    assert res.status_code == 502
    assert res.get_json()["reason"] == "model-failed"


def test_empty_answer_is_reported(client, monkeypatch, models_env):
    res = ask_with(client, monkeypatch, "phi", Reply({"choices": [{"message": {"content": "   "}}]}))
    assert res.status_code == 502 and res.get_json()["reason"] == "empty"


def test_timeout_is_offline_not_a_crash(client, monkeypatch, models_env):
    monkeypatch.setenv("SUBBY_PROVIDER", "phi")

    def slow(*args, **kwargs):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(ai_providers.requests, "post", slow)
    res = client.post("/subby/ask", json={"question": "Synthetic test"})
    assert res.status_code == 502
    assert res.get_json()["reason"] == "model-offline"


def test_good_replies_still_work(client, monkeypatch, models_env):
    phi = ask_with(client, monkeypatch, "phi", Reply({"choices": [{"message": {"content": "Hi from Phi"}}]}))
    assert phi.get_json()["answer"] == "Hi from Phi"
    gemini = ask_with(client, monkeypatch, "gemini",
                      Reply({"candidates": [{"content": {"parts": [{"text": "Hi "}, {"text": "there"}]}}]}))
    assert gemini.get_json()["answer"] == "Hi there"


def test_invalid_fallback_setting_is_ignored_not_a_crash(client, monkeypatch, models_env):
    monkeypatch.setenv("SUBBY_PROVIDER", "phi")
    monkeypatch.setenv("SUBBY_FALLBACK", "invalid-provider")
    calls = []

    def offline(url, **kwargs):
        calls.append(url)
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ai_providers.requests, "post", offline)
    res = client.post("/subby/ask", json={"question": "Synthetic test"})
    assert res.status_code == 502
    assert res.get_json() == {"answer": None, "reason": "model-offline", "provider": "phi"}
    assert all("googleapis" not in url for url in calls)  # still no silent cloud call


# ---------- RUNTIME-1: editing never silently loses saved values -------------

FULL = {
    "name": "Review plan", "amount": "10.00", "currency": "USD", "cycle": "monthly",
    "next_renewal_at": "2026-11-01", "lead_days": "14,7,3",
    "manage_url": "https://example.test/manage", "notes": "first",
}
# Exactly the fields the UI-lane edit form sends (Antigravity d74d2ac).
UI_FORM_FIELDS = ["name", "amount", "currency", "cycle", "next_renewal_at", "remind_days", "notes"]


def saved_plan(user, app):
    user.post("/subscriptions/new", data=FULL)
    with app.app_context():
        return Subscription.query.one().id


def current(app):
    with app.app_context():
        return Subscription.query.one()


def test_simpler_form_keeps_lead_days_and_manage_link(user, app):
    sub_id = saved_plan(user, app)
    form = {**{k: FULL[k] for k in UI_FORM_FIELDS if k in FULL}, "remind_days": "14", "notes": "edited"}
    assert user.post(f"/subscriptions/{sub_id}/edit", data=form).status_code == 302
    item = current(app)
    assert item.lead_days == "14,7,3"
    assert item.manage_url == "https://example.test/manage"
    assert item.notes == "edited"


def test_unchanged_full_edit_changes_nothing(user, app):
    sub_id = saved_plan(user, app)
    user.post(f"/subscriptions/{sub_id}/edit", data=FULL)
    item = current(app)
    assert (item.lead_days, item.manage_url, item.notes, item.amount) == (
        "14,7,3", "https://example.test/manage", "first", Decimal("10.00"))


def test_deliberate_clear_of_manage_link_and_notes(user, app):
    sub_id = saved_plan(user, app)
    user.post(f"/subscriptions/{sub_id}/edit", data={**FULL, "manage_url": "", "notes": ""})
    item = current(app)
    assert item.manage_url == "" and item.notes == ""


def test_changing_the_single_number_replaces_the_list(user, app):
    sub_id = saved_plan(user, app)
    form = {k: FULL[k] for k in UI_FORM_FIELDS if k in FULL}
    user.post(f"/subscriptions/{sub_id}/edit", data={**form, "remind_days": "5"})
    assert current(app).lead_days == "5"


def test_multi_lead_update(user, app):
    sub_id = saved_plan(user, app)
    user.post(f"/subscriptions/{sub_id}/edit", data={**FULL, "lead_days": "30, 1"})
    item = current(app)
    assert item.lead_days == "30,1" and item.remind_days == 30


def test_form_with_only_a_name_keeps_everything_else(user, app):
    sub_id = saved_plan(user, app)
    user.post(f"/subscriptions/{sub_id}/edit", data={"name": "Renamed"})
    item = current(app)
    assert item.name == "Renamed"
    assert item.amount == Decimal("10.00") and item.next_renewal_at == date(2026, 11, 1)
    assert item.lead_days == "14,7,3"


# ---------- RUNTIME-2 (backend part): totals never depend on the page --------

def test_list_page_gets_account_wide_totals(user, app, monkeypatch):
    for n in range(25):
        user.post("/subscriptions/new", data={**FULL, "name": f"Synthetic plan {n:02d}"})
    data = user.get("/dashboard.json").get_json()["projected"]
    assert data == [{"currency": "USD", "count": 25, "monthly": "250.00", "yearly": "3000.00"}]

    # Catch what the list page hands its template, for several pages/searches.
    seen = []
    monkeypatch.setattr("app.subscriptions.render_template",
                        lambda template, **context: seen.append(context) or "ok")
    for url in ["/subscriptions/", "/subscriptions/?page=2", "/subscriptions/?q=plan%2003"]:
        user.get(url)
    assert [len(c["items"]) for c in seen] == [20, 5, 1]  # the page/search differs...
    for context in seen:  # ...but the account totals don't
        assert context["totals"] == [{"currency": "USD", "count": 25,
                                      "monthly": Decimal("250.00"), "yearly": Decimal("3000.00")}]


def test_search_covers_the_whole_account(user, app):
    for n in range(25):
        user.post("/subscriptions/new", data={**FULL, "name": f"Synthetic plan {n:02d}"})
    page = user.get("/subscriptions/?q=Synthetic%20plan%2024").get_data(as_text=True)
    assert "Synthetic plan 24" in page  # on page 2 without a search, found by the server


def test_settings_json_reads_the_saved_settings(user):
    user.post("/settings", data={"timezone": "Asia/Ho_Chi_Minh", "reminder_hour": "7",
                                 "reminders_enabled": "on", "channels": "email"})
    assert user.get("/settings.json").get_json() == {
        "timezone": "Asia/Ho_Chi_Minh", "reminders_enabled": True, "reminder_hour": 7,
        "channels": ["email"], "available_channels": ["email"],
    }
