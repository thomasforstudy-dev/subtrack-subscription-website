import os
import secrets
from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

from app.config import database_url
from app.schema import EXPECTED_TABLES, schema_issues

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"

DEV_SECRET = "dev-only-change-me"


def safe_link(url: str) -> str:
    """Return the URL only if it is a normal https link, otherwise ''."""
    url = url.strip()
    return url if url.startswith("https://") else ""


def tone(name: str) -> int:
    """The same colour (0-5) for the same name on every page, so "Netflix"
    always gets the same tile colour (see .tone-0 ... .tone-5 in style.css)."""
    return sum(map(ord, (name or "").strip().lower())) % 6


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
    # Bill uploads are at most 10 MB; much bigger requests are refused before
    # they are read (the page then says so, see too_big below).
    app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024
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

    from app.read_aloud import MAX_PDF_BYTES
    from app.security import check_csrf, csrf_token

    @app.before_request
    def bigger_upload_limit():
        # Read aloud takes book-sized PDFs; every other form keeps the 11 MB limit.
        # This must run before check_csrf, which reads the form (and so the upload).
        if request.endpoint == "read_aloud.show":
            request.max_content_length = MAX_PDF_BYTES + 1024 * 1024  # + room for the form fields

    app.before_request(check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from app.i18n import say, t, ui_lang
    from app.mailer import inbox_url

    # One language per page: {{ t("Tiếng Việt", "English") }} in every template,
    # {{ say(message) }} for messages the code writes in English.
    app.jinja_env.globals.update(t=t, say=say, ui_lang=ui_lang, inbox_url=inbox_url, tone=tone)

    from app.admin import bp as admin_bp
    from app.api import bp as api_bp
    from app.api_tokens import bp as api_tokens_bp
    from app.auth import bp as auth_bp
    from app.bill_jobs import process_documents_command
    from app.bill_review import bp as bill_review_bp
    from app.bills import bp as bills_bp
    from app.calendar import bp as calendar_bp
    from app.dashboard import bp as dashboard_bp
    from app.forecast import bp as forecast_bp
    from app.links import bp as links_bp
    from app.main import bp as main_bp
    from app.oauth import bp as oauth_bp
    from app.read_aloud import bp as read_aloud_bp
    from app.reminders import send_reminders_command
    from app.roulette import bp as roulette_bp
    from app.settings import bp as settings_bp
    from app.subby import bp as subby_bp
    from app.subscriptions import bp as subscriptions_bp
    from app.tools import bp as tools_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(oauth_bp)
    app.register_blueprint(subby_bp)
    app.register_blueprint(bills_bp)
    app.register_blueprint(bill_review_bp)
    app.register_blueprint(api_tokens_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(forecast_bp)
    app.register_blueprint(read_aloud_bp)
    app.register_blueprint(roulette_bp)
    app.cli.add_command(send_reminders_command)
    app.cli.add_command(process_documents_command)

    @app.url_defaults
    def version_static_files(endpoint, values):
        """Add ?v=<time the file last changed> to every /static/ link.

        Cloudflare tells browsers to keep CSS/JS for 4 hours. Without this, after
        an update a browser shows the new pages with the old style.css, and the
        layout falls apart. A new number = a new address = a fresh download.
        """
        if endpoint != "static" or "filename" not in values:
            return
        try:
            values["v"] = int((Path(app.static_folder) / values["filename"]).stat().st_mtime)
        except OSError:
            pass  # a missing file just gets no number (and a 404, as before)

    @app.get("/favicon.ico")
    def favicon():
        # Browsers and search engines ask for /favicon.ico at the site root.
        return app.send_static_file("favicon.ico")

    @app.errorhandler(404)
    def not_found(error):
        # A friendly page with the mascot. JSON addresses keep the plain error,
        # because scripts read them, not people; the extension API answers in JSON.
        if request.path.startswith("/api/"):
            return jsonify(error="not-found"), 404
        if request.path.endswith(".json"):
            return error
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_big(error):
        if request.path == "/bills/upload":
            flash("That file is bigger than 10 MB. Please upload a smaller one.")
            return redirect(url_for("bills.list_bills"))
        if request.path == "/tools/read-aloud/":
            flash("That PDF is bigger than 40 MB.")
            return redirect(url_for("read_aloud.show"))
        return error

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

            from app.links import fill_missing_fingerprints

            db.create_all()
            upgrade_sqlite(db.engine)
            fill_missing_fingerprints()

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
        except Exception:
            # Driver errors can include connection strings and credentials.
            click.secho("Could not connect. Check the local database configuration and service.", fg="red")
            raise SystemExit(1)

        problems = schema_issues(engine)
        if problems:
            click.secho(
                "Connected, but schema is incomplete: " + "; ".join(problems) + ". "
                "Run the numbered scripts through database/06_bills.sql in SSMS.",
                fg="yellow",
            )
            raise SystemExit(1)
        click.secho("OK: connected; required tables, columns and indexes exist.", fg="green")

    return app
