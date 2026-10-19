"""Exercise the repaired UI's actual controls against the integrated backend."""

from app import db
from app.models import Subscription
from tests.conftest import PASSWORD, sign_up
from tests.html_helpers import Page
from tests.test_review_repairs import FULL


def test_rendered_edit_form_roundtrip_keeps_all_fields(user, app):
    user.post("/subscriptions/new", data=FULL)
    with app.app_context():
        item_id = Subscription.query.one().id
    form = Page(user.get(f"/subscriptions/{item_id}/edit").get_data(as_text=True)).form_with("lead_days")
    assert form["fields"]["lead_days"] == "14,7,3"
    assert form["fields"]["manage_url"] == FULL["manage_url"]
    assert form["fields"]["csrf_token"]
    assert user.post(f"/subscriptions/{item_id}/edit", data=form["fields"], csrf=False).status_code == 302
    with app.app_context():
        item = db.session.get(Subscription, item_id)
        assert (item.lead_days, item.manage_url, item.notes) == ("14,7,3", FULL["manage_url"], FULL["notes"])


def test_validation_error_preserves_controls_and_does_not_save(user, app):
    values = {**FULL, "amount": "NaN", "notes": "keep me <private>", "lead_days": "30, 7, 1"}
    response = user.post("/subscriptions/new", data=values)
    assert response.status_code == 200
    fields = Page(response.get_data(as_text=True)).form_with("lead_days")["fields"]
    for field, value in values.items():
        assert fields[field] == value
    with app.app_context():
        assert Subscription.query.count() == 0


def test_server_search_and_pager_show_rows_beyond_first_twenty(user):
    for number in range(25):
        user.post("/subscriptions/new", data={**FULL, "name": f"Synthetic plan {number:02d}"})
    first = Page(user.get("/subscriptions/?sort=name").get_data(as_text=True))
    second_response = user.get("/subscriptions/?sort=name&page=2")
    second = Page(second_response.get_data(as_text=True))
    assert first.subscription_names == [f"Synthetic plan {n:02d}" for n in range(20)]
    assert second.subscription_names == [f"Synthetic plan {n:02d}" for n in range(20, 25)]
    filtered = user.get("/subscriptions/?q=Synthetic+plan+24&sort=name")
    assert Page(filtered.get_data(as_text=True)).subscription_names == ["Synthetic plan 24"]
    assert user.get("/dashboard.json").get_json()["projected"][0]["monthly"] == "250.00"
    assert 'name="q"' in filtered.get_data(as_text=True)
    # This must be useful before JavaScript loads, and remain account-wide on a search.
    assert "USD 250.00 / tháng" in filtered.get_data(as_text=True)
    assert "25 gói đang hoạt động" in filtered.get_data(as_text=True)


def test_settings_survive_login_and_stay_separate_between_accounts(app):
    me, other = app.test_client(), app.test_client()
    sign_up(me, email="mine@example.com")
    sign_up(other, email="other@example.com")
    before = other.get("/settings.json").get_json()
    me.post("/settings", data={"timezone": "America/New_York", "reminder_hour": "7",
                                "reminders_enabled": "on", "channels": "email"})
    me.post("/logout")
    me.post("/login", data={"identifier": "mine@example.com", "password": PASSWORD})
    own = me.get("/settings.json").get_json()
    assert (own["timezone"], own["reminder_hour"]) == ("America/New_York", 7)
    assert other.get("/settings.json").get_json() == before
    page = me.get("/settings").get_data(as_text=True)
    fields = Page(page).form_with("timezone")["fields"]
    assert fields["timezone"] == "America/New_York"
    assert fields["reminder_hour"] == "7"
