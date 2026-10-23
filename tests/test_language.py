"""One language per page: English mode shows no Vietnamese, Vietnamese mode no stray English."""

import re
from html.parser import HTMLParser

import pytest

from app.messages_vi import to_vietnamese
from app.mailer import inbox_url

from .conftest import PASSWORD, sign_up

VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
# English left inside Vietnamese text, like "Thuế (Tax)" or "Hiển thị (Show)".
MIXED = re.compile(r"\((?:[A-Z][a-z]+)(?:[ &/-]+[A-Za-z]+)*\)")


class Visible(HTMLParser):
    """Text a visitor sees or hears: text, placeholders, titles, aria-labels.
    Texts carrying data-vi + data-en count in the chosen language (app-ui.js swaps them)."""

    VOID = {"br", "img", "input", "meta", "link", "hr", "source", "wbr"}

    def __init__(self, lang):
        super().__init__(convert_charrefs=True)
        self.lang, self.texts, self.stack = lang, [], []  # stack of (tag, hidden or swapped)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        swapped = "data-vi" in a and "data-en" in a
        if swapped:
            self.texts.append(a["data-" + self.lang])
        for name in ("placeholder", "title", "aria-label", "alt"):
            if a.get(name):
                self.texts.append(a[name])
        if tag not in self.VOID:
            self.stack.append((tag, swapped or tag in ("script", "style", "svg", "code")))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if data.strip() and not any(hide for _, hide in self.stack):
            self.texts.append(" ".join(data.split()))


def wrong_language(html: str, lang: str) -> list[str]:
    parser = Visible(lang)
    parser.feed(html)
    if lang == "en":
        return [t for t in parser.texts if VI_CHARS.search(t)]
    return [t for t in parser.texts if VI_CHARS.search(t) and MIXED.search(t)]


PAGES_SIGNED_OUT = ["/", "/login", "/register", "/forgot-password", "/no-such-page"]
PAGES_SIGNED_IN = ["/dashboard", "/subscriptions/", "/subscriptions/new", "/bills/", "/bills/new", "/links/",
                   "/calendar/", "/settings", "/settings/tokens", "/tools/", "/tools/forecast/",
                   "/tools/read-aloud/", "/tools/food-roulette/"]


@pytest.mark.parametrize("lang", ["en", "vi"])
def test_every_page_speaks_one_language(app, lang):
    visitor = app.test_client()
    visitor.set_cookie("ui_lang", lang)
    member = app.test_client()
    sign_up(member, "lang@example.com")
    member.set_cookie("ui_lang", lang)
    member.post("/subscriptions/new", data={"name": "Netflix", "amount": "9.99", "currency": "USD", "cycle": "monthly",
                                            "next_renewal_at": "2026-12-01", "lead_days": "7"})
    problems = {}
    for client, paths in ((visitor, PAGES_SIGNED_OUT), (member, PAGES_SIGNED_IN)):
        for path in paths:
            html = client.get(path).get_data(as_text=True)
            assert f'<html lang="{lang}"' in html, path
            found = wrong_language(html, lang)
            if found:
                problems[path] = found[:5]
    assert problems == {}


def test_server_messages_follow_the_language(app):
    sign_up(app.test_client(), "who@example.com")
    for lang, expected in (("en", "Wrong email/username or password."), ("vi", "Sai email/tên đăng nhập hoặc mật khẩu.")):
        client = app.test_client()
        client.set_cookie("ui_lang", lang)
        page = client.post("/login", data={"identifier": "who@example.com", "password": "Wrong-password-1"}).get_data(as_text=True)
        assert expected in page, lang


def test_messages_with_a_changing_part_are_translated():
    assert to_vietnamese("Too many tries. Please wait 15 minutes, or reset your password.") == \
        "Thử quá nhiều lần. Vui lòng chờ 15 phút, hoặc đặt lại mật khẩu."
    assert to_vietnamese("Your password also needs an upper-case letter and a number.") == \
        "Mật khẩu cần thêm một chữ in hoa và một chữ số."
    assert to_vietnamese("Please check: The items add up to 10.00, but the total says 12.00.") == \
        "Vui lòng kiểm tra: Các món cộng lại 10.00, nhưng tổng ghi 12.00."
    assert to_vietnamese("Something new nobody translated.") == "Something new nobody translated."


def test_language_cookie_is_the_switch(app):
    client = app.test_client()
    client.delete_cookie("ui_lang")
    assert '<html lang="vi"' in client.get("/login").get_data(as_text=True)  # Vietnamese is the default
    client.set_cookie("ui_lang", "en")
    page = client.get("/login").get_data(as_text=True)
    assert '<html lang="en"' in page and "Welcome back" in page


def test_open_gmail_button_for_known_webmail(app):
    assert inbox_url("someone@gmail.com")["name"] == "Gmail"
    assert inbox_url("someone@outlook.com")["url"].startswith("https://outlook.live.com")
    assert inbox_url("student@st.buh.edu.vn") is None
    client = app.test_client()
    sign_up(client, "toan@gmail.com")
    page = client.get("/subscriptions/").get_data(as_text=True)
    assert "https://mail.google.com/mail/u/0/#inbox" in page and 'target="_blank"' in page and "Open Gmail" in page


def test_register_and_login_pages(app):
    client = app.test_client()
    register = client.get("/register").get_data(as_text=True)
    # Email first, and the username box can't be auto-filled with a saved login email.
    assert register.index('name="email"') < register.index('name="username"')
    assert 'autocomplete="nickname"' in register
    assert 'class="pwd-rules"' in register and 'data-rule="special"' in register  # ticks while typing
    assert ">Show<" not in register and ">Hiện<" not in register  # an eye icon, not a big button
    login = client.get("/login").get_data(as_text=True)
    assert "Preview account states" not in login and "auth-states-preview" not in login


def test_subscriptions_page_has_no_dashboard_buttons(user):
    page = user.get("/subscriptions/").get_data(as_text=True)
    assert "Full Account Dashboard" not in page and "Open Dashboard" not in page and "DECIMAL" not in page.upper().split("<SCRIPT")[0]
