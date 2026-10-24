from app import db
from app.links import normalize_tags, normalize_url, url_fingerprint
from app.models import Link
from tests.conftest import sign_up


def no_lookup(monkeypatch):
    # Tests must not visit real websites.
    monkeypatch.setattr("app.links.fetch_preview", lambda url: {})


def test_links_page_needs_login(client):
    assert client.get("/links/").status_code == 302


def test_save_search_tag_pin_delete(user, app, monkeypatch):
    no_lookup(monkeypatch)
    assert user.post("/links/new", data={"url": "docs.python.org/3/", "tags": "School, python"}).status_code == 302
    user.post("/links/new", data={"url": "https://flask.palletsprojects.com", "title": "Flask docs", "tags": "python, tools"})

    with app.app_context():
        first = Link.query.filter_by(url="https://docs.python.org/3/").one()
        assert first.title == "docs.python.org"          # fallback when lookup finds nothing
        assert first.tags == "school, python"
        first_id = first.id

    assert b"Flask docs" in user.get("/links/?q=flask").data
    page = user.get("/links/?tag=school").data
    assert b"docs.python.org" in page and b"Flask docs" not in page
    assert b"No links match" in user.get("/links/?q=50%25").data

    user.post(f"/links/{first_id}/pin")
    html = user.get("/links/").data.decode()
    assert html.index("docs.python.org") < html.index("Flask docs")

    user.post(f"/links/{first_id}/delete")
    with app.app_context():
        assert db.session.get(Link, first_id) is None


def test_title_filled_from_page_when_empty(user, app, monkeypatch):
    monkeypatch.setattr(
        "app.links.fetch_preview",
        lambda url: {"title": "Stitch - Design with AI", "description": "Turn ideas into UI."},
    )
    user.post("/links/new", data={"url": "https://stitch.withgoogle.com/?pli=1"})
    user.post("/links/new", data={"url": "https://example.com", "title": "My own title"})
    with app.app_context():
        stitch = Link.query.filter(Link.url.contains("stitch")).one()
        assert stitch.title == "Stitch - Design with AI"
        assert stitch.notes == "Turn ideas into UI."
        assert Link.query.filter_by(url="https://example.com").one().title == "My own title"


def test_preview_endpoint(user, monkeypatch):
    monkeypatch.setattr("app.links.fetch_preview", lambda url: {"title": "Hello"})
    assert user.post("/links/preview", data={"url": "example.com"}).get_json() == {"title": "Hello"}
    assert user.post("/links/preview", data={"url": "javascript:alert(1)"}).get_json() == {}


def test_other_users_cannot_touch_my_links(app, monkeypatch):
    no_lookup(monkeypatch)
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    me.post("/links/new", data={"url": "https://secret.example.com", "title": "Secret"})
    with app.app_context():
        link_id = Link.query.one().id
    assert other.get(f"/links/{link_id}/edit").status_code == 404
    assert other.post(f"/links/{link_id}/delete").status_code == 404
    assert other.post(f"/links/{link_id}/pin").status_code == 404
    assert b"Secret" not in other.get("/links/").data


def test_normalize_url():
    assert normalize_url("example.com") == ("https://example.com", None)
    assert normalize_url("site.com:8000/x")[0] == "https://site.com:8000/x"
    # Private and local addresses are refused when saving (Codex security review S1).
    for private in ("localhost:8000/x", "http://127.0.0.1:5000/", "http://192.168.1.1/admin",
                    "http://169.254.169.254/", "http://[::1]/", "http://printer.local/"):
        assert normalize_url(private)[0] == "", private
    for bad in ["", "javascript:alert(1)", "mailto:a@b.c", "file:///c:/x", "ftp://x", "http://"]:
        assert normalize_url(bad)[1] is not None, bad


def test_normalize_tags():
    assert normalize_tags(" School, PYTHON ,school,, ") == "school, python"


def test_fingerprint_ignores_small_differences():
    same = [
        "https://www.Example.com/a/?utm_source=x&b=2&a=1#top",
        "http://example.com/a?a=1&b=2",
        "https://example.com:443/a/?a=1&b=2&fbclid=123",
    ]
    assert len({url_fingerprint(u) for u in same}) == 1
    assert url_fingerprint("https://example.com/a") != url_fingerprint("https://example.com/b")
    assert url_fingerprint("https://example.com/a?id=1") != url_fingerprint("https://example.com/a?id=2")
    assert url_fingerprint("https://example.com:8080/") != url_fingerprint("https://example.com/")


def test_same_link_twice_is_refused(user, app, monkeypatch):
    no_lookup(monkeypatch)
    user.post("/links/new", data={"url": "https://docs.python.org/3/", "title": "Python docs"})
    res = user.post("/links/new", data={"url": "http://www.docs.python.org/3?utm_source=mail"})
    assert "already saved this link as" in res.get_data(as_text=True)
    with app.app_context():
        assert Link.query.count() == 1


def test_other_users_can_save_the_same_link(app, monkeypatch):
    no_lookup(monkeypatch)
    me, other = app.test_client(), app.test_client()
    sign_up(me, "me@example.com")
    sign_up(other, "other@example.com")
    me.post("/links/new", data={"url": "https://example.com", "title": "Mine"})
    other.post("/links/new", data={"url": "https://example.com", "title": "Theirs"})
    with app.app_context():
        assert Link.query.count() == 2


def test_editing_a_link_is_not_a_duplicate_of_itself(user, app, monkeypatch):
    no_lookup(monkeypatch)
    user.post("/links/new", data={"url": "https://example.com", "title": "Mine"})
    with app.app_context():
        link_id = Link.query.one().id
    res = user.post(f"/links/{link_id}/edit", data={"url": "https://example.com/", "title": "Renamed"})
    assert res.status_code == 302
    with app.app_context():
        assert Link.query.one().title == "Renamed"


def test_icon_falls_back_to_the_sites_own_favicon(user, app, monkeypatch):
    no_lookup(monkeypatch)
    user.post("/links/new", data={"url": "https://example.com/page", "title": "Typed title"})
    with app.app_context():
        assert Link.query.one().favicon_url == "https://example.com/favicon.ico"


def test_icon_from_the_page_is_kept(user, app, monkeypatch):
    monkeypatch.setattr("app.links.fetch_preview",
                        lambda url: {"title": "Page", "icon": "https://cdn.example.com/i.png"})
    user.post("/links/new", data={"url": "https://example.com/page"})
    with app.app_context():
        assert Link.query.one().favicon_url == "https://cdn.example.com/i.png"
