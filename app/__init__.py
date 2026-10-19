import os
import secrets
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

from app.config import database_url

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

EXPECTED_TABLES = {"users", "subscriptions", "reminder_logs", "links", "auth_tokens"}
DEV_SECRET = "dev-only-change-me"


def safe_link(url: str) -> str:
    """Return the URL only if it is a normal https link, otherwise ''."""
    url = url.strip()
    return url if url.startswith("https://") else ""


def secret_key(production: bool) -> str:
    """The key that signs login cookies. Anyone who knows it can fake a login,
    so the live site refuses to start with a missing, short or sample key."""
    key = os.getenv("SECRET_KEY", "").strip()
    if production and (len(key) < 32 or key == DEV_SECRET):
        raise RuntimeError(
            "SECRET_KEY in .env is missing or too short. Make one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\" "
            "(or set APP_ENV=development for testing on this PC)."
        )
    return key or DEV_SECRET


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Anything except APP_ENV=development counts as the live site.
    production = os.getenv("APP_ENV", "production").strip().lower() != "development"
    app.config["SECRET_KEY"] = secret_key(production)
    app.config.update(
        # Login cookies: JavaScript can't read them, other sites' forms don't
        # get them, and on the live site they only travel over HTTPS.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=production,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=production,
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url(app.instance_path)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Test each pooled connection before use, so the app recovers by itself
    # if SQL Server restarts.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        # The cookie holds "id:fingerprint" (see User.get_id). An old
        # fingerprint means the password changed, so that login has ended.
        raw_id, _, key = user_id.partition(":")
        user = db.session.get(User, int(raw_id)) if raw_id.isdigit() else None
        if user is not None and secrets.compare_digest(user.session_key, key):
            return user
        return None

    from app.security import check_csrf, csrf_token

    app.before_request(check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.links import bp as links_bp
    from app.main import bp as main_bp
    from app.oauth import bp as oauth_bp
    from app.subby import bp as subby_bp
    from app.subscriptions import bp as subscriptions_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(subby_bp)

    @app.context_processor
    def contact_links():
        # Where Subby sends people when it can't answer. Set in .env.
        return {
            "contact": {
                "messenger": safe_link(os.getenv("MESSENGER_URL", "")),
                "zalo": safe_link(os.getenv("ZALO_URL", "")),
            }
        }

    with app.app_context():
        # SQL Server tables come from the numbered scripts in database/.
        # SQLite makes its own tables, then adds columns that older files lack.
        if db.engine.dialect.name == "sqlite":
            from app.migrate import upgrade_sqlite

            db.create_all()
            upgrade_sqlite(db.engine)

    @app.cli.command("check-db")
    def check_db():
        """Check the app can reach the database and the tables exist."""
        engine = db.engine
        click.echo(f"Database type: {engine.dialect.name}")
        try:
            with engine.connect() as conn:
                if engine.dialect.name == "mssql":
                    row = conn.execute(
                        text("SELECT @@SERVERNAME, DB_NAME(), SUSER_SNAME()")
                    ).one()
                    click.echo(f"Server: {row[0]}  Database: {row[1]}  Login: {row[2]}")
                else:
                    conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - show any connection error
            click.secho(f"Could not connect: {exc}", fg="red")
            raise SystemExit(1)

        found = set(inspect(engine).get_table_names())
        missing = EXPECTED_TABLES - found
        if missing:
            click.secho(
                f"Connected, but tables are missing: {', '.join(sorted(missing))}. "
                "Run the scripts in database/ (01_schema.sql, 02_accounts.sql, ...) in SSMS.",
                fg="yellow",
            )
            raise SystemExit(1)
        click.secho("OK: connected and all tables exist.", fg="green")

    return app
