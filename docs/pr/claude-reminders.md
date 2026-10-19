# [claude] Reminders: checked subscriptions, dashboard, settings, send-reminders job

Branch: `claude/reminders` → `main`, **stacked on `claude/accounts`** (merge that first).
Draft — don't merge without the owner.

## Objective
Section B: make the main promise real — an email before each renewal — on top
of subscriptions that are validated, and a dashboard that never mixes
currencies or pretends a renewal date was a payment.

## What changed
- **Subscriptions**: Decimal money (max 2 decimals, no floats), 3-letter
  currency, year 2000–2100, up to 3 lead times (`lead_days` = "14,7,3"; old
  `remind_days` still accepted), optional http/https `manage_url`, notes ≤ 2000.
  Errors re-show the form with what was typed. List: search, active/archived/all,
  sort, 20 per page, restore. Editing no longer un-archives.
- **Renewal rules** (`app/schedule.py`): month-end uses the last day without
  drifting (`billing_day`), 29 Feb → 28 Feb and back in leap years, weekly = 7 days.
- **Expected vs actual**: when a renewal date passes, the job moves it forward
  and saves the old date in `renewals` as **expected** (not paid). The dashboard
  lets the user mark it paid / not charged. "Actual spending" waits for real bills.
- **Dashboard** `/dashboard` + `/dashboard.json`: projected monthly/yearly per
  currency, next 30 days, expected charges of the last 60 days.
- **Settings** `/settings`: time zone (IANA), reminders on/off, local hour, channels (email).
- **`flask send-reminders`** (`app/reminders.py`, run by Task Scheduler, never
  in a web request): roll → plan → claim → send.
  - unique key (subscription, renewal date, channel, lead days) — can't plan twice
  - conditional-UPDATE claim — two runs can't send the same row
  - Resend `Idempotency-Key = subtrack-reminder-<id>` reused on every retry
  - failed → retry after 10/20/40/80 min, max 5 tries; "sending" for > 15 min = crashed → retried
  - several milestones due at once → only the closest is sent, the rest "skipped"
  - re-checks before sending: still active, same date, reminders on, email confirmed
  - email not set up → rows stay pending, the command exits with an error
  - **No exactly-once claim**: a crash between Resend accepting and our "sent"
    update is covered by Resend's 24 h idempotency only.

## Schema
- users: `timezone`, `reminders_enabled`, `reminder_hour`, `reminder_channels`
- subscriptions: `billing_day`, `lead_days`, `manage_url`
- new tables `renewals`, `reminders`; `reminder_logs` kept untouched (unused)
- SQL Server: `database/03_reminders.sql` (rerunnable, no DROP)
- SQLite: added automatically at start-up (`app/migrate.py`)

## New package
`tzdata==2026.5` — Windows has no time-zone database, and `zoneinfo` needs one.

## How to deploy (owner)
1. Back up `instance\subtrack.db`. Merge `claude/accounts` first, then this.
2. `.venv\Scripts\python -m pip install -r requirements.txt` (adds tzdata), restart SubTrack-Server.
3. In `.env`: `DEFAULT_TIMEZONE=Asia/Ho_Chi_Minh`; for real email `RESEND_API_KEY` + `MAIL_FROM`.
4. Confirm your email (banner), set your time zone in Settings.
5. Codex: Task Scheduler every 30 min → `.venv\Scripts\python -m flask --app app send-reminders`.

## Tests actually run
- `pytest`: **165 passed** (SQLite, Python 3.14). New: `test_schedule.py`,
  `test_reminders.py`, `test_dashboard.py`, more in `test_subscriptions.py` and `test_migrate.py`.
- Rehearsed on a copy of the live SQLite file in production mode: upgrade OK,
  2 subscriptions kept (`lead_days` "7", `billing_day` set), `/dashboard`,
  `/dashboard.json`, `/subscriptions/`, `/settings`, `/links/`, `/admin/users` → 200,
  `send-reminders --dry-run` plans 0 (owner's email not confirmed yet — correct).

## Not verified
- `03_reminders.sql` not run on SQL Server (not reachable on this PC).
- No real Resend delivery; Task Scheduler job not created (PC setup lane).
- "Two runs at once" is tested by claiming the same row twice in one process,
  not by two real processes against SQL Server.

## UI lane
Style `dashboard.html`, `settings.html`, the list's search/filter/sort/pager and the
new form fields. Everything the templates get is in `docs/CONTRACT.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
