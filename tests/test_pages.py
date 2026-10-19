"""The landing page, the restyled pages and Subby's contact buttons."""


def test_visitors_see_the_landing_story(client):
    res = client.get("/")
    assert res.status_code == 200
    page = res.get_data(as_text=True)
    assert "rush hour" in page
    assert 'href="/register"' in page  # "Get started free" goes to sign up
    assert "landing.js" in page


def test_logged_in_users_skip_the_landing(user):
    res = user.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/subscriptions/")


def test_every_page_has_subby(client, user):
    for url in ["/subscriptions/", "/links/"]:
        page = user.get(url).get_data(as_text=True)
        assert "data-subby" in page, url


def test_auth_pages_render(client):
    for url in ["/login", "/register", "/forgot-password"]:
        res = client.get(url)
        assert res.status_code == 200
        assert 'name="csrf_token"' in res.get_data(as_text=True)
    assert 'name="identifier"' in client.get("/login").get_data(as_text=True)


def test_contact_buttons_use_https_links_only(client, monkeypatch):
    monkeypatch.setenv("MESSENGER_URL", "https://m.me/example")
    monkeypatch.setenv("ZALO_URL", "javascript:alert(1)")
    page = client.get("/login").get_data(as_text=True)
    assert 'href="https://m.me/example"' in page
    assert "javascript:" not in page
    assert ">Zalo<" not in page  # unsafe/missing link: no button at all
