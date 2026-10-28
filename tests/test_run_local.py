"""run_local.bat makes a .env that works on http://127.0.0.1."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_new_env_is_development_mode():
    # Without APP_ENV=development the app treats the copy as the live site:
    # login cookies go over HTTPS only, so logging in on localhost fails.
    script = (ROOT / "run_local.bat").read_text(encoding="utf-8")
    writes_env = re.search(r"open\('\.env','w'\)\.write\((.*)\)\"", script)
    assert writes_env, "run_local.bat should create .env"
    assert r"\nAPP_ENV=development\n" in writes_env.group(1)
