"""Confirm-email and reset-password links. Emails go to a list, never to real people."""

import re
from datetime import timedelta

from app import db, mailer
from app.models import AuthToken, User
from tests.conftest import PASSWORD, sign_up


def last_link(path_part: str) -> str:
    """The path of the newest emailed link containing `path_part`."""
    assert mailer.sent, "no email was sent"
    match = re.search(r"https?://[^/\s]+(/" + path_part + r"/\S+)", mailer.sent[-1].text)
    assert match, mailer.sent[-1].text
    return match.group(1)


def make_old(app, purpose):
    with app.app_context():
        for token in AuthToken.query.filter_by(purpose=purpose):
            token.expires_at -= timedelta(days=2)
        db.session.commit()


# ---------- confirm email ----------------------------------------------------

def test_sign_up_sends_a_confirm_link(client, app):
    sign_up(client, "me@example.com")
    assert mailer.sent[-1].to == "me@example.com"
    link = last_link("verify-email")
    # Opening the link (or an email scanner opening it) changes nothing.
    assert "Confirm my email" in client.get(link).get_data(as_text=True)
    with app.app_context():
        assert not User.query.one().email_verified
    # Pressing the button confirms.
    client.post(link)
    with app.app_context():
        assert User.query.one().email_verified


def test_confirm_link_works_once(client, app):
    sign_up(client, "me@example.com")
    link = last_link("verify-email")
    client.post(link)
    res = client.post(link)
    assert res.headers["Location"].endswith("/login")
    assert "work any more" in client.get(link).get_data(as_text=True)


def test_expired_confirm_link_is_refused(client, app):
    sign_up(client, "me@example.com")
    link = last_link("verify-email")
    make_old(app, "verify_email")
    client.post(link)
    with app.app_context():
        assert not User.query.one().email_verified


def test_link_for_an_old_address_does_not_confirm_a_new_one(client, app):
    sign_up(client, "me@example.com")
    link = last_link("verify-email")
    with app.app_context():
        User.query.one().email = "changed@example.com"
        db.session.commit()
    client.post(link)
    with app.app_context():
        assert not User.query.one().email_verified


def test_only_hashes_of_tokens_are_stored(client, app):
    sign_up(client, "me@example.com")
    raw = last_link("verify-email").rsplit("/", 1)[1]
    with app.app_context():
        stored = AuthToken.query.one().token_hash
    assert raw not in stored and len(stored) == 64


def test_resend_is_limited(user):
    for _ in range(5):
        user.post("/verify-email/resend")
    count = len(mailer.sent)
    user.post("/verify-email/resend")
    assert len(mailer.sent) == count


def test_unconfirmed_users_see_the_banner(user):
    assert "Please confirm your email" in user.get("/subscriptions/").get_data(as_text=True)


# ---------- forgot / reset password -----------------------------------------

def forgot(client, email):
    return client.post("/forgot-password", data={"email": email}, follow_redirects=True)


def test_forgot_password_gives_the_same_answer_for_everyone(client):
    sign_up(client, "me@example.com")
    client.post("/logout")
    mailer.sent.clear()
    known = forgot(client, "me@example.com").get_data(as_text=True)
    unknown = forgot(client, "nobody@example.com").get_data(as_text=True)
    assert "If that email has an account" in known
    assert "If that email has an account" in unknown
    assert [m.to for m in mailer.sent] == ["me@example.com"]  # only real accounts get mail


def test_reset_password_flow(client, app):
    sign_up(client, "me@example.com")
    client.post("/logout")
    forgot(client, "me@example.com")
    link = last_link("reset-password")

    # A weak password is refused and the link still works afterwards.
    res = client.post(link, data={"password": "weak", "confirm": "weak"})
    assert "12 to 128 characters" in res.get_data(as_text=True)

    new = "Another-Pass-42"
    res = client.post(link, data={"password": new, "confirm": new})
    assert res.headers["Location"].endswith("/login")
    with app.app_context():
        user = User.query.one()
        assert user.check_password(new)
        assert not user.check_password(PASSWORD)
        assert user.email_verified  # the link reached their inbox

    # The link works only once.
    again = client.post(link, data={"password": "Third-Pass-42!", "confirm": "Third-Pass-42!"})
    assert again.headers["Location"].endswith("/forgot-password")


def test_reset_cancels_older_reset_links(client, app):
    sign_up(client, "me@example.com")
    client.post("/logout")
    forgot(client, "me@example.com")
    first = last_link("reset-password")
    forgot(client, "me@example.com")
    second = last_link("reset-password")
    client.post(second, data={"password": "Another-Pass-42", "confirm": "Another-Pass-42"})
    res = client.post(first, data={"password": "Third-Pass-42!", "confirm": "Third-Pass-42!"})
    assert res.headers["Location"].endswith("/forgot-password")


def test_expired_reset_link_is_refused(client, app):
    sign_up(client, "me@example.com")
    client.post("/logout")
    forgot(client, "me@example.com")
    link = last_link("reset-password")
    make_old(app, "reset_password")
    res = client.post(link, data={"password": "Another-Pass-42", "confirm": "Another-Pass-42"})
    assert res.headers["Location"].endswith("/forgot-password")
    with app.app_context():
        assert User.query.one().check_password(PASSWORD)


def test_reset_logs_out_other_browsers(app):
    laptop, phone = app.test_client(), app.test_client()
    sign_up(phone, "me@example.com")
    forgot(laptop, "me@example.com")
    link = last_link("reset-password")
    laptop.post(link, data={"password": "Another-Pass-42", "confirm": "Another-Pass-42"})
    assert phone.get("/subscriptions/").status_code == 302


def test_forgot_password_when_email_is_not_set_up(client, monkeypatch):
    monkeypatch.setenv("MAIL_BACKEND", "none")
    sign_up(client, "me@example.com")
    client.post("/logout")
    known = forgot(client, "me@example.com").get_data(as_text=True)
    unknown = forgot(client, "nobody@example.com").get_data(as_text=True)
    assert "aren&#39;t switched on yet" in known
    assert "aren&#39;t switched on yet" in unknown


def test_forgot_password_is_rate_limited(client):
    for _ in range(5):
        forgot(client, "nobody@example.com")
    assert client.post("/forgot-password", data={"email": "x@example.com"}).status_code == 429
