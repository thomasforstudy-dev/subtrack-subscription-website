"""Which language a visitor reads: Vietnamese (default) or English.

The VI / EN button in the top bar saves a small cookie, `ui_lang`, so the
server builds each page and each message in that one language (no mix).
Templates and Python both use t("Vietnamese text", "English text").
"""

from flask import has_request_context, request

LANG_COOKIE = "ui_lang"


def ui_lang() -> str:
    """"en" if the visitor chose English, otherwise "vi"."""
    if has_request_context() and request.cookies.get(LANG_COOKIE) == "en":
        return "en"
    return "vi"


def t(vi: str, en: str) -> str:
    """Pick the text for the visitor's language."""
    return en if ui_lang() == "en" else vi


def say(message: str) -> str:
    """A server message (written in English in the code) in the visitor's language."""
    if ui_lang() == "en":
        return message
    from app.messages_vi import to_vietnamese

    return to_vietnamese(message)
