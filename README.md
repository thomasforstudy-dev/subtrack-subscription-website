# SubTrack

Never get charged for a subscription you forgot about. SubTrack keeps your
subscriptions and useful links in one place and reminds you before anything renews.

**Stack:** Python · Flask · Microsoft SQL Server (T-SQL) · Cloudflare Tunnel

## Features

- [x] Sign up / log in (passwords stored only as hashes)
- [x] Subscriptions: amount, billing cycle, next renewal, reminder lead time
- [x] Pinned links: save, tag, search, and pin websites to the top — the page title is filled in automatically
- [x] Admin page listing registered users
- [ ] Email reminders before renewal
- [ ] Dashboard with monthly spend
- [ ] Google Calendar buttons + calendar feed
- [ ] AI helper
- [ ] Chrome extension

## Run it on Windows

### 1. One-time setup

1. **SQL Server Express** must be running and set to start automatically
   (`services.msc` → *SQL Server (SQLEXPRESS)* → Startup type: **Automatic**).
2. Install **Microsoft ODBC Driver 18 for SQL Server** (x64) if it isn't installed.
   Check with: `Get-OdbcDriver -Name "*SQL Server*"`
3. Create the database: open SSMS, connect to `localhost\SQLEXPRESS`,
   open [`database/01_schema.sql`](database/01_schema.sql) and press **Execute**.

### 2. Start the app

```powershell
cd C:\Users\buith\Projects\subtrack
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit .env (see below)
flask --app app check-db    # should print: OK: connected and all tables exist.
flask --app app run --debug
```

Open http://127.0.0.1:5000. The first account created becomes **admin**.

### `.env` settings

| Setting | What it is |
|---|---|
| `SECRET_KEY` | Long random string — `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_SERVER` | `'localhost\SQLEXPRESS'` (keep the single quotes). Empty = use a local SQLite test file |
| `DB_NAME` | `SubTrack` |
| `DB_USER` / `DB_PASSWORD` | Leave empty to log in with your Windows account |

## Tests

Double-click `run_tests.bat` (or run `.venv\Scripts\python -m pytest -q`). All tests must pass before committing.

## Working with AI tools

Rules for Claude, Codex, Gemini and Antigravity are in [`AGENTS.md`](AGENTS.md); the plan and work log are in [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Database

All tables, constraints, indexes and views are defined in T-SQL in
[`database/01_schema.sql`](database/01_schema.sql):

| Table / view | Holds |
|---|---|
| `users` | Accounts (email, password hash, admin flag) |
| `subscriptions` | Each user's subscriptions and renewal dates |
| `links` | Each user's pinned links and tags |
| `reminder_logs` | Every reminder sent — a unique constraint stops duplicates |
| `vw_upcoming_renewals` | Active subscriptions with days left until renewal |
| `vw_monthly_spend` | Monthly cost per user, with weekly/yearly converted |

Try it in SSMS:

```sql
USE SubTrack;
SELECT * FROM dbo.vw_upcoming_renewals ORDER BY days_left;
SELECT * FROM dbo.vw_monthly_spend;
```
