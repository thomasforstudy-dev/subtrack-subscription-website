"""The mascot (our logo with a face), the friendly 404 page and the logo as the site icon."""

import json
from pathlib import Path

from .conftest import sign_up

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"


def test_missing_page_shows_the_lost_mascot(client):
    response = client.get("/no-such-page")
    page = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "mascot-lost" in page and "Không tìm thấy trang này" in page
    assert 'href="/"' in page  # signed out: back to the home page


def test_someone_elses_item_is_just_not_found(client):
    sign_up(client, "owner@example.com")
    client.post("/subscriptions/new", data={"name": "Owner secret plan", "amount": "9.99", "currency": "USD",
                                            "cycle": "monthly", "next_renewal_at": "2026-12-01", "lead_days": "3"})
    client.post("/logout")
    sign_up(client, "other@example.com")
    response = client.get("/subscriptions/1/edit")
    page = response.get_data(as_text=True)
    assert response.status_code == 404 and "mascot-lost" in page
    assert "Owner secret plan" not in page  # the friendly page never says whose item it was
    assert 'href="/dashboard' in page  # signed in: back to the dashboard


def test_json_addresses_keep_the_plain_404(user):
    response = user.get("/bills/jobs/999.json")
    assert response.status_code == 404
    assert "mascot" not in response.get_data(as_text=True)


def test_new_user_is_welcomed_by_the_mascot(user):
    page = user.get("/dashboard").get_data(as_text=True)
    assert "mascot-hi" in page and "Chào mừng bạn đến AllOutFree!" in page
    user.post("/subscriptions/new", data={"name": "Netflix", "amount": "260000", "currency": "VND", "cycle": "monthly",
                                          "next_renewal_at": "2026-12-01", "lead_days": "3"})
    assert "Chào mừng bạn đến AllOutFree!" not in user.get("/dashboard").get_data(as_text=True)


def test_empty_lists_show_the_mascot(user):
    assert "mascot-hi" in user.get("/subscriptions/").get_data(as_text=True)
    assert "mascot-hi" in user.get("/links/").get_data(as_text=True)
    assert "mascot-hi" in user.get("/bills/").get_data(as_text=True)
    assert "mascot-look" in user.get("/subscriptions/?q=nothing-like-this").get_data(as_text=True)


def test_the_logo_is_the_site_icon_everywhere(client):
    page = client.get("/").get_data(as_text=True)
    for name in ("favicon.ico", "favicon.svg", "apple-touch-icon.png", "manifest.webmanifest"):
        assert f"/static/{name}" in page
    icon = client.get("/favicon.ico")
    assert icon.status_code == 200 and icon.data[:4] == b"\x00\x00\x01\x00"  # a real .ico file
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["theme_color"] == "#f2602d"
    for entry in manifest["icons"]:
        assert (STATIC / entry["src"].removeprefix("/static/")).is_file(), entry["src"]
    assert {entry["purpose"] for entry in manifest["icons"]} == {"any", "maskable"}
