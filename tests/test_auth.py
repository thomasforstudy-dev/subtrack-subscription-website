"""Sign up with email + password (with the confirm box)."""

from app.models import User


def register(client, password="password123", confirm="password123", email="new@example.com"):
    return client.post(
        "/register", data={"email": email, "password": password, "confirm": confirm}
    )


def test_sign_up_works_when_passwords_match(client, app):
    res = register(client)
    assert res.status_code == 302
    with app.app_context():
        assert User.query.filter_by(email="new@example.com").count() == 1


def test_sign_up_refuses_different_passwords(client, app):
    res = register(client, confirm="something-else")
    assert res.status_code == 200
    assert "don&#39;t match" in res.get_data(as_text=True)
    with app.app_context():
        assert User.query.count() == 0


def test_sign_up_refuses_short_password(client, app):
    res = register(client, password="short", confirm="short")
    assert "at least 8 characters" in res.get_data(as_text=True)
    with app.app_context():
        assert User.query.count() == 0


def test_sign_up_form_has_confirm_box(client):
    assert 'name="confirm"' in client.get("/register").get_data(as_text=True)
