"""Confirm an email with the 6-digit code from the confirm email (or its link, as before)."""

import re
from datetime import timedelta

from app import db, mailer
from app.models import EmailCode, User, utcnow

from .conftest import sign_up


def last_code() -> str:
    assert mailer.sent, "no email was sent"
    found = re.search(r"code is: (\d{6})", mailer.sent[-1].text)
    assert found, mailer.sent[-1].text
    return found.group(1)


def verified(app, email="a@example.com") -> bool:
    with app.app_context():
        return User.query.filter_by(email=email).one().email_verified


def test_email_has_a_code_and_the_right_code_confirms(user, app):
    code = last_code()
    assert mailer.sent[-1].subject.startswith(code)
    assert "/verify-email/" in mailer.sent[-1].text  # the link still works too
    page = user.get("/subscriptions/").get_data(as_text=True)
    assert 'name="code"' in page and 'autocomplete="one-time-code"' in page
    response = user.post("/verify-email/code", data={"code": f"{code[:3]} {code[3:]}", "next": "/links/"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/links/")
    assert verified(app)
    with app.app_context():  # used up, and only a hash was ever stored
        row = EmailCode.query.one()
        assert row.used_at is not None and code not in row.code_hash and len(row.code_hash) == 64


def test_wrong_code_does_nothing_and_five_wrong_cancels_it(user, app):
    code = last_code()
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        user.post("/verify-email/code", data={"code": wrong})
    assert not verified(app)
    user.post("/verify-email/code", data={"code": code})  # even the right one is cancelled now
    assert not verified(app)
    user.post("/verify-email/resend")  # a fresh email gives a fresh code and fresh tries
    user.post("/verify-email/code", data={"code": last_code()})
    assert verified(app)


def test_only_the_newest_code_works(user, app):
    old = last_code()
    user.post("/verify-email/resend")
    new = last_code()
    if old != new:
        user.post("/verify-email/code", data={"code": old})
        assert not verified(app)
    user.post("/verify-email/code", data={"code": new})
    assert verified(app)


def test_a_code_belongs_to_one_account(client, app):
    sign_up(client, "first@example.com")
    first_code = last_code()
    client.post("/logout")
    sign_up(client, "second@example.com")
    client.post("/verify-email/code", data={"code": first_code})
    assert not verified(app, "second@example.com") and not verified(app, "first@example.com")


def test_expired_code_and_code_as_link_are_refused(user, app):
    code = last_code()
    assert user.get(f"/verify-email/1:{code}").status_code == 200  # the page opens...
    user.post(f"/verify-email/1:{code}")  # ...but a code is never a link
    assert not verified(app)
    with app.app_context():
        row = EmailCode.query.one()
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    user.post("/verify-email/code", data={"code": code})
    assert not verified(app)


def test_code_for_an_old_address_is_refused(user, app):
    code = last_code()
    with app.app_context():  # the address changed after the code was sent
        User.query.one().email = "new@example.com"
        db.session.commit()
    user.post("/verify-email/code", data={"code": code})
    assert not verified(app, "new@example.com")


def test_code_needs_login_and_csrf(client, user, app):
    code = last_code()
    assert user.post("/verify-email/code", data={"code": code}, csrf=False).status_code == 400
    user.post("/logout")
    response = user.post("/verify-email/code", data={"code": code})
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    assert not verified(app)


def test_outside_links_are_never_used_as_next(user, app):
    response = user.post("/verify-email/code", data={"code": last_code(), "next": "https://evil.example/"})
    assert response.headers["Location"].endswith("/subscriptions/")
