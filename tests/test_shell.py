"""The header, account menu, phone tab bar and footer on every page (base.html)."""


def test_visitors_get_login_links_and_a_footer_but_no_app_menus(client):
    page = client.get("/login").get_data(as_text=True)
    assert 'class="site-footer"' in page
    assert "/register" in page and "/forgot-password" in page
    assert "data-nav-pills" not in page  # nothing to navigate before logging in
    assert 'class="tabbar"' not in page


def test_logged_in_header_marks_the_current_page(user):
    page = user.get("/bills/").get_data(as_text=True)
    assert 'aria-current="page" data-nav-target="bills"' in page
    assert page.count('aria-current="page"') == 3  # the header link, the left rail and the phone tab


def test_account_menu_logs_out_with_a_csrf_form(user):
    page = user.get("/dashboard").get_data(as_text=True)
    menu = page.split("data-user-menu", 1)[1].split("</details>", 1)[0]
    assert 'action="/logout"' in menu and 'name="csrf_token"' in menu
    assert "a_user" in menu  # the username from sign_up


def test_phone_tab_bar_has_the_add_button(user):
    page = user.get("/dashboard").get_data(as_text=True)
    tabbar = page.split('class="tabbar"', 1)[1].split("</nav>", 1)[0]
    assert 'class="tab-fab" href="/subscriptions/new"' in tabbar
    assert "data-nav-target" not in tabbar  # only the header link carries it


def test_landing_keeps_its_own_single_footer(client):
    page = client.get("/").get_data(as_text=True)
    assert page.count('role="contentinfo"') == 1


def test_static_files_get_a_version_so_updates_are_never_half_old(client):
    """Cloudflare lets browsers keep CSS for 4 hours: a new ?v= after every
    change makes them fetch the new file together with the new page."""
    import re

    page = client.get("/login").get_data(as_text=True)
    css = re.search(r'/static/style\.css\?v=(\d+)"', page)
    assert css, "style.css must carry ?v=<number>"
    assert client.get(f"/static/style.css?v={css.group(1)}").status_code == 200


def test_outside_links_in_the_footer_are_safe(client):
    page = client.get("/login").get_data(as_text=True)
    footer = page.split('class="site-footer"', 1)[1]
    assert 'href="https://github.com/' in footer
    assert 'rel="noopener noreferrer"' in footer
