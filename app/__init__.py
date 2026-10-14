import os
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

EXPECTED_TABLES = {"users", "subscriptions", "reminder_logs", "links"}


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
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
        return db.session.get(User, int(user_id))

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.links import bp as links_bp
    from app.main import bp as main_bp
    from app.subscriptions import bp as subscriptions_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(subscriptions_bp)
    app.register_blueprint(links_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        # SQL Server tables come from database/01_schema.sql.
        # The SQLite test file creates its own tables.
        if db.engine.dialect.name == "sqlite":
            db.create_all()

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
                "Run database/01_schema.sql in SSMS.",
                fg="yellow",
            )
            raise SystemExit(1)
        click.secho("OK: connected and all tables exist.", fg="green")

    return app
