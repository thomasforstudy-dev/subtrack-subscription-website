"""Connection-string contracts; these tests never connect to SQL Server."""

import os
import socket
from urllib.parse import parse_qs, urlsplit

import pytest

from app.config import database_url


def test_app_dotenv_loader_cannot_read_environment_files(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.delenv("SUBTRACK_TEST_DOTENV_PROBE", raising=False)
    test_env = tmp_path / "synthetic.env"
    test_env.write_text("SUBTRACK_TEST_DOTENV_PROBE=synthetic-only\n", encoding="utf-8")
    assert app_module.load_dotenv(test_env) is False
    assert os.getenv("SUBTRACK_TEST_DOTENV_PROBE") is None


def test_real_external_socket_connections_are_blocked():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        with pytest.raises(OSError, match="must mock external network"):
            connection.connect(("198.51.100.1", 443))


def test_sql_server_takes_precedence_and_escapes_password(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_SERVER", r"localhost\SQLEXPRESS")
    monkeypatch.setenv("DB_NAME", "SubTrackTest")
    monkeypatch.setenv("DB_USER", "test-user")
    monkeypatch.setenv("DB_PASSWORD", "demo;=with}braces")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    url = database_url(str(tmp_path))
    assert url.startswith("mssql+pyodbc:///")
    odbc = parse_qs(urlsplit(url).query)["odbc_connect"][0]
    assert "DATABASE=SubTrackTest" in odbc
    assert "PWD={demo;=with}}braces}" in odbc
    assert "Trusted_Connection" not in odbc


def test_sql_server_windows_identity_does_not_add_password(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_SERVER", r"localhost\SQLEXPRESS")
    monkeypatch.setenv("DB_USER", "")
    url = database_url(str(tmp_path))
    odbc = parse_qs(urlsplit(url).query)["odbc_connect"][0]
    assert "Trusted_Connection=yes" in odbc
    assert "UID=" not in odbc and "PWD=" not in odbc


def test_sqlite_url_and_default_stay_in_selected_test_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_SERVER", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    assert database_url(str(tmp_path)) == "sqlite:///:memory:"
    monkeypatch.delenv("DATABASE_URL")
    assert database_url(str(tmp_path)) == "sqlite:///" + str(tmp_path / "subtrack.db")
