"""Brand logos for well-known services, so "Netflix Premium" shows the Netflix
mark instead of a plain "N" tile.

The icons are files in static/brands/ from Simple Icons (simpleicons.org,
CC0 licence), stored with the app so no page loads images from other sites.
A name matches when it contains one of the keywords (case doesn't matter);
anything else keeps its coloured letter tile.
"""

# (keywords, icon file in static/brands/, the brand's own colour)
BRANDS = [
    (("netflix",), "netflix", "#e50914"),
    (("spotify",), "spotify", "#1db954"),
    (("youtube",), "youtube", "#ff0000"),
    (("chatgpt", "openai"), "openai", "#10a37f"),
    (("icloud",), "icloud", "#3693f3"),
    (("claude", "anthropic"), "claude", "#d97757"),
    (("elevenlabs", "eleven labs"), "elevenlabs", "#16142b"),
    (("cloudflare",), "cloudflare", "#f38020"),
    (("grab",), "grab", "#00b14f"),
    (("shopee",), "shopee", "#ee4d2d"),
    (("canva",), "canva", "#00c4cc"),
    (("apple music",), "applemusic", "#fa243c"),
    (("notion",), "notion", "#16142b"),
    (("github",), "github", "#181717"),
    (("google drive",), "googledrive", "#1fa463"),
    (("google",), "google", "#4285f4"),  # Google One, Google AI Pro...
    (("capcut", "tiktok"), "tiktok", "#16142b"),
]


def brand(name: str) -> dict | None:
    """{"slug": ..., "color": ...} for a known service, else None."""
    text = (name or "").lower()
    for keywords, slug, color in BRANDS:
        if any(word in text for word in keywords):
            return {"slug": slug, "color": color}
    return None
