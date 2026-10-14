"""Settings read from the .env file.

Which database the app uses:
  1. DB_SERVER is set      -> Microsoft SQL Server (the live setup)
  2. DATABASE_URL is set   -> whatever that URL points to
  3. neither               -> a local SQLite file in instance/ (quick testing)
"""

import os
from pathlib import Path
from urllib.parse import quote_plus


def _odbc_value(value: str) -> str:
    # Wrap in braces so passwords with ; or = don't break the connection string.
    return "{" + value.replace("}", "}}") + "}"


def sql_server_url() -> str | None:
    server = os.getenv("DB_SERVER", "").strip()
    if not server:
        return None

    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={os.getenv('DB_NAME', 'SubTrack').strip()}",
        "Encrypt=yes",
        # SQL Server on your own PC uses a self-signed certificate.
        "TrustServerCertificate=yes",
    ]

    user = os.getenv("DB_USER", "").strip()
    if user:
        parts.append(f"UID={_odbc_value(user)}")
        parts.append(f"PWD={_odbc_value(os.getenv('DB_PASSWORD', ''))}")
    else:
        # Log in with the Windows account that runs the app.
        parts.append("Trusted_Connection=yes")

    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))


def database_url(instance_path: str) -> str:
    url = sql_server_url()
    if url:
        return url

    url = os.getenv("DATABASE_URL", "").strip()
    if url and not url.startswith("sqlite:///instance/"):
        return url

    return "sqlite:///" + str(Path(instance_path) / "subtrack.db")
