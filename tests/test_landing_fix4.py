"""Fix_4 (28 Oct): the landing page's white cards stay readable in dark mode,
and the hero has a real first-open entrance."""

from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "app" / "static" / "landing.css").read_text(encoding="utf-8")


def test_white_cards_set_their_own_dark_text():
    block = CSS[CSS.index(".light-stat,\n.sub-card-in,"):]
    block = block[:block.index("}")]
    for card in (".sub-card-in", ".row", ".when", ".countdown span", ".sort-chip", ".bill-source-mini"):
        assert card in block
    assert "--text: #16142b" in block and "color: var(--text)" in block


def test_hero_has_an_entrance_and_fading_trails():
    assert "@keyframes card-arrive" in CSS and "var(--fx), var(--fy)" in CSS
    assert "@keyframes card-trail" in CSS


def test_landing_page_still_loads(app):
    page = app.test_client().get("/").get_data(as_text=True)
    assert "landing.css" in page and "data-rush" in page
