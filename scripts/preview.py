"""Loopback-only synthetic integration preview; never reads the owner's .env."""

import argparse
import html
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    instance = ROOT / "instance"
    instance.mkdir(exist_ok=True)
    database = instance / "integration-preview.db"
    os.environ.update(DB_SERVER="", DATABASE_URL="sqlite:///" + str(database), APP_ENV="development",
                      SECRET_KEY=secrets.token_hex(32), MAIL_BACKEND="memory", RESEND_API_KEY="",
                      GEMINI_API_KEY="", SUBBY_PROVIDER="fake", SUBBY_FALLBACK="",
                      GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="", GITHUB_CLIENT_ID="",
                      GITHUB_CLIENT_SECRET="", MESSENGER_URL="", ZALO_URL="")
    with patch("dotenv.load_dotenv", return_value=False):
        from app import create_app, db
        from app.models import Subscription, User, utcnow
        app = create_app()
    from app.ai_providers import FakeProvider

    original_fake_chat = FakeProvider.chat

    def fake_preview_chat(self, system, history, question, temperature):
        # Deterministic selectors for checking the REAL account-tool routes.
        # The banner/provider metadata still explicitly labels the model as fake.
        if question.lower() == "show my upcoming renewals":
            return '[TOOL] {"name":"list_upcoming_renewals","args":{"days":30}}'
        if question.lower() == "draft a reminder":
            draft = {"name": "Synthetic draft", "amount": "9.99", "currency": "USD",
                     "cycle": "monthly", "next_renewal_at": (date.today() + timedelta(days=7)).isoformat()}
            return "[TOOL] " + json.dumps({"name": "create_reminder_draft", "args": draft})
        return original_fake_chat(self, system, history, question, temperature)

    FakeProvider.chat = fake_preview_chat
    access_path = instance / "preview-access.json"
    with app.app_context():
        user = User.query.filter_by(username="review_demo").first()
        if user is None:
            password = secrets.token_urlsafe(18) + "Aa1!"
            user = User(username="review_demo", email="review-demo@example.com", timezone="Asia/Ho_Chi_Minh",
                        email_verified_at=utcnow())
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            for number in range(25):
                renewal = date.today() + timedelta(days=number + 1)
                db.session.add(Subscription(user_id=user.id, name=f"Synthetic plan {number:02d}",
                    amount=Decimal("10.00"), currency="USD", cycle="monthly", next_renewal_at=renewal,
                    billing_day=renewal.day, lead_days="14,7,3", remind_days=14,
                    manage_url="https://example.com/manage", notes="Synthetic preview data only"))
            db.session.commit()
            access_path.write_text(json.dumps({"username": "review_demo", "password": password}), encoding="utf-8")
    revision = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()

    @app.after_request
    def preview_banner(response):
        response.headers["Cache-Control"] = "no-store"
        if response.mimetype == "text/html":
            banner = (
                '<div role="status" style="padding:12px;background:#fff0bf;color:#342500;'
                'text-align:center;position:relative;z-index:10000">'
                '<strong>Integration preview — synthetic data only</strong><br>'
                'Backend: Flask · Database: SQLite · Mail: memory (no sends) · AI: fake · '
                f'Revision: {html.escape(revision)}</div>'
            )
            body = response.get_data(as_text=True)
            response.set_data(re.sub(r"(<body\b[^>]*>)", lambda match: match[1] + banner, body, count=1))
        return response

    print(f"Preview: http://127.0.0.1:{args.port}; synthetic access: {access_path}", flush=True)
    from waitress import serve

    serve(app, host="127.0.0.1", port=args.port, threads=4)


if __name__ == "__main__":
    main()
