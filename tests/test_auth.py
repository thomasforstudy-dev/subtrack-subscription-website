"""Accounts: sign up, log in / out, lockout, CSRF, admin, sessions."""

import pytest

from app import create_app, db
from app.models import Subscription, User
from app.security import safe_next_url
from tests.conftest import PASSWORD, sign_up


def register(client, **fields):
    data = {"username": "newbie", "email": "new@example.com", "password": PASSWORD, "confirm": PASSWORD}
    data.update(fields)
    return client.post("/register", data=data)


def login(client, identifier, password=PASSWORD, field="identifier", **kwargs):
    return client.post("/login", data={field: identifier, "password": password}, **kwargs)


# ---------- sign up ----------------------------------------------------------

def test_sign_up_makes_a_normal_account(client, app):
    res = register(client, username="New_Bie")
    assert res.status_code == 302
    with app.app_context():
        user = User.query.one()
        assert user.username == "new_bie"  # stored in lower case
        assert user.email == "new@example.com"
        assert not user.is_admin  # the first account is no longer admin
        assert not user.email_verified


@pytest.mark.parametrize(
    "password, message",
    [
        ("Short1!", "12 to 128 characters"),
        ("alllowercase123!", "upper-case letter"),
        ("NoNumbersHere!!", "a number"),
        ("NoSpecialChars123", "special character"),
        ("A1!" + "x" * 130, "12 to 128 characters"),
    ],
)
def test_sign_up_refuses_weak_passwords(client, app, password, message):
    res = register(client, password=password, confirm=password)
    assert message in res.get_data(as_text=True)
    with app.app_context():
        assert User.query.count() == 0


def test_sign_up_refuses_different_passwords(client, app):
    res = register(client, confirm="Something-else-123")
    assert "don&#39;t match" in res.get_data(as_text=True)
    with app.app_context():
        assert User.query.count() == 0


@pytest.mark.parametrize("username", ["ab", "has space", "dấu", "x" * 31, "semi;colon", ""])
def test_sign_up_refuses_bad_usernames(client, app, username):
    register(client, username=username)
    with app.app_context():
        assert User.query.count() == 0


def test_full_width_letters_become_normal_letters(client, app):
    register(client, username="ｔｏａｎ")
    with app.app_context():
        assert User.query.one().username == "toan"


def test_usernames_and_emails_are_unique(client, app):
    register(client)
    client.post("/logout")
    page = register(client, username="NEWBIE", email="other@example.com").get_data(as_text=True)
    assert "username is taken" in page
    page = register(client, username="someone", email="NEW@example.com").get_data(as_text=True)
    assert "already registered" in page
    with app.app_context():
        assert User.query.count() == 1


def test_sign_up_form_has_the_contract_fields(client):
    page = client.get("/register").get_data(as_text=True)
    for name in ["username", "email", "password", "confirm", "csrf_token"]:
        assert f'name="{name}"' in page


# ---------- log in / out -----------------------------------------------------

def test_log_in_with_email_or_username(client, app):
    sign_up(client, "me@example.com", username="me_me")
    client.post("/logout")
    assert login(client, "ME@example.com").status_code == 302
    client.post("/logout")
    assert login(client, "Me_Me").status_code == 302
    client.post("/logout")
    # The old field name "email" still works.
    assert login(client, "me@example.com", field="email").status_code == 302


def test_wrong_password_and_unknown_account_look_the_same(client):
    sign_up(client, "me@example.com")
    client.post("/logout")
    wrong = login(client, "me@example.com", "Wrong-password-1").get_data(as_text=True)
    unknown = login(client, "nobody@example.com", "Wrong-password-1").get_data(as_text=True)
    assert "Wrong email/username or password." in wrong
    assert "Wrong email/username or password." in unknown


def test_too_many_wrong_passwords_locks_for_a_while(client):
    sign_up(client, "me@example.com")
    client.post("/logout")
    for _ in range(5):
        assert login(client, "me@example.com", "Wrong-password-1").status_code == 200
    # Even the right password is refused during the lockout.
    res = login(client, "me@example.com")
    assert res.status_code == 429
    assert "Too many tries" in res.get_data(as_text=True)


def test_lockout_is_per_account_and_address(client):
    sign_up(client, "me@example.com")
    client.post("/logout")
    for _ in range(5):
        login(client, "me@example.com", "Wrong-password-1", environ_base={"REMOTE_ADDR": "198.51.100.7"})
    # The real owner, from their own address, can still log in.
    assert login(client, "me@example.com", environ_base={"REMOTE_ADDR": "198.51.100.8"}).status_code == 302


def test_log_out_needs_post_and_token(user):
    assert user.get("/logout").status_code == 405
    assert user.post("/logout", csrf=False).status_code == 400
    assert user.get("/subscriptions/").status_code == 200  # still logged in
    user.post("/logout")
    assert user.get("/subscriptions/").status_code == 302


def test_login_goes_back_to_the_page_you_wanted(client):
    sign_up(client, "me@example.com")
    client.post("/logout")
    res = client.post("/login?next=/links/", data={"identifier": "me@example.com", "password": PASSWORD})
    assert res.headers["Location"] == "/links/"


@pytest.mark.parametrize(
    "target",
    ["https://evil.example/", "//evil.example", "/\\evil.example", "javascript:alert(1)", "/ok\nSet-Cookie:x"],
)
def test_login_never_redirects_to_other_sites(target):
    assert safe_next_url(target) is None


def test_safe_next_allows_own_pages():
    assert safe_next_url("/links/?q=x") == "/links/?q=x"


# ---------- CSRF -------------------------------------------------------------

def test_forms_without_the_token_are_refused(user, app):
    res = user.post("/subscriptions/new", data={"name": "Netflix"}, csrf=False)
    assert res.status_code == 400
    with app.app_context():
        assert Subscription.query.count() == 0


def test_wrong_token_is_refused(user):
    res = user.post("/subscriptions/new", data={"name": "Netflix", "csrf_token": "guess"}, csrf=False)
    assert res.status_code == 400


def test_javascript_can_send_the_token_in_a_header(user, monkeypatch):
    monkeypatch.setattr("app.links.fetch_preview", lambda url: {"title": "Hi"})
    token = user.csrf_token()
    res = user.post("/links/preview", data={"url": "example.com"}, headers={"X-CSRF-Token": token}, csrf=False)
    assert res.get_json() == {"title": "Hi"}


def test_every_page_with_a_form_has_the_token(user):
    for url in ["/subscriptions/", "/subscriptions/new", "/links/", "/links/new"]:
        page = user.get(url).get_data(as_text=True)
        assert page.count('name="csrf_token"') >= 1, url


# ---------- sessions ---------------------------------------------------------

def test_changing_the_password_logs_out_other_browsers(app):
    laptop, phone = app.test_client(), app.test_client()
    sign_up(laptop, "me@example.com")
    login(phone, "me@example.com")
    assert phone.get("/subscriptions/").status_code == 200
    with app.app_context():
        user = User.query.one()
        user.set_password("Brand-new-pass-1")
        db.session.commit()
    assert phone.get("/subscriptions/").status_code == 302


def test_old_style_login_cookies_stop_working(user, app):
    with user.session_transaction() as sess:
        sess["_user_id"] = "1"  # the format before this change: no fingerprint
    assert user.get("/subscriptions/").status_code == 302


# ---------- admin ------------------------------------------------------------

def test_admin_page_is_for_admins_only(user, app):
    assert user.get("/admin/users").status_code == 403
    with app.app_context():
        runner = app.test_cli_runner()
        result = runner.invoke(args=["make-admin", "a@example.com"])
        assert "now an admin" in result.output
    assert user.get("/admin/users").status_code == 200


def test_cannot_remove_the_last_admin(user, app):
    runner = app.test_cli_runner()
    runner.invoke(args=["make-admin", "a_user"])  # by username works too
    result = runner.invoke(args=["make-admin", "a_user", "--remove"])
    assert result.exit_code != 0
    assert "last admin" in result.output
    with app.app_context():
        assert User.query.one().is_admin


def test_make_admin_unknown_account(app):
    result = app.test_cli_runner().invoke(args=["make-admin", "ghost@example.com"])
    assert result.exit_code != 0


# ---------- settings ---------------------------------------------------------

def test_live_site_refuses_a_weak_secret_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'p.db'}")
    monkeypatch.setenv("APP_ENV", "production")
    for weak in ["", "short", "dev-only-change-me"]:
        monkeypatch.setenv("SECRET_KEY", weak)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app()


def test_live_site_uses_https_only_cookies(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'p.db'}")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    app = create_app()
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
