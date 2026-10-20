"""Preview boundaries without connecting to SQL Server or loading owner files."""

import pytest

from scripts import sql_preview, sql_web_checks
from scripts.sql_load_check import percentile


@pytest.mark.parametrize("database", ["SubTrack", "master_other", "untrusted;DATABASE=SubTrack"])
def test_preview_refuses_any_nonallowlisted_database(database):
    with pytest.raises(ValueError, match="allowlisted"):
        sql_preview.dsn(database)


def test_preview_connection_is_explicit_sql_with_windows_authentication():
    value = sql_preview.dsn()
    assert "SERVER=localhost\\SQLEXPRESS" in value
    assert "DATABASE=SubTrack_CodexMainPreview_20261020" in value
    assert "Trusted_Connection=yes" in value and "PWD=" not in value
    assert "SubTrackCodexSQLPreview" in value


def test_main_preview_cookies_are_distinct_from_live_and_previous_previews():
    assert sql_preview.SESSION_COOKIE_NAME not in {"session", "subtrack_sql_preview_session"}
    assert sql_preview.REMEMBER_COOKIE_NAME not in {"remember_token", "subtrack_sql_preview_remember"}
    assert sql_preview.SESSION_COOKIE_NAME != sql_preview.REMEMBER_COOKIE_NAME


def test_preview_health_rejects_sqlite(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"provider": "sqlite", "database": sql_preview.DATABASE}

    monkeypatch.setattr(sql_web_checks.Client, "get", lambda self, path: Response())
    with pytest.raises(AssertionError, match="Wrong preview/database"):
        sql_web_checks.health()


def test_load_percentiles_are_measured_order_statistics():
    assert percentile([10, 1, 4, 2, 3], 0.5) == 3
    assert percentile([10, 1, 4, 2, 3], 0.95) == 10
    assert percentile([], 0.95) is None


def test_repeated_web_checks_use_distinct_valid_generated_documents():
    import io
    from PIL import Image
    first = sql_web_checks.synthetic_png("synthetic-first-run")
    second = sql_web_checks.synthetic_png("synthetic-second-run")
    assert first != second
    for data in [first, second]:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            assert image.format == "PNG" and image.size == (8, 8)
