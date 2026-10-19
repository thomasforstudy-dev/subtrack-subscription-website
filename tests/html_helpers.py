"""Read actual form controls/table rows rather than unrelated overview/demo text."""

from html.parser import HTMLParser


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.subscription_names = []
        self.forms = []
        self._form = None
        self._textarea = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and "data-sub-row" in attrs:
            self.subscription_names.append(attrs["data-name"])
        if tag == "form":
            self._form = {"action": attrs.get("action", ""), "fields": {}}
            self.forms.append(self._form)
        if self._form is None:
            return
        if tag == "input" and attrs.get("name"):
            kind = attrs.get("type", "text")
            if kind in ("checkbox", "radio") and "checked" not in attrs:
                return
            self._form["fields"][attrs["name"]] = attrs.get("value", "")
        elif tag == "select":
            self._select = attrs.get("name")
        elif tag == "option" and getattr(self, "_select", None):
            if "selected" in attrs or self._select not in self._form["fields"]:
                self._form["fields"][self._select] = attrs.get("value", "")
        elif tag == "textarea":
            self._textarea = attrs.get("name")
            if self._textarea:
                self._form["fields"][self._textarea] = ""

    def handle_data(self, text):
        if self._form is not None and self._textarea:
            self._form["fields"][self._textarea] += text

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "textarea":
            self._textarea = None
        elif tag == "select":
            self._select = None

    def form_with(self, field):
        return next(form for form in self.forms if field in form["fields"])
