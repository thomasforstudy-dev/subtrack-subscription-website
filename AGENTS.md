# SubTrack — rules for every AI working on this project

This file is read automatically by Codex, Antigravity and Gemini CLI, and by
Claude through `CLAUDE.md`. Everyone follows the same rules.

**The owner** is a 2nd-year student and a Python beginner, building this for
a portfolio. **Deadline: Sun 25 Oct 2026.** Keep the code simple enough that
he can explain every line in an interview.

## What SubTrack is

A website where users sign up, add their subscriptions (Netflix, Spotify, ...)
and get reminded by email **before** they renew, so they can renew or cancel in time.
Users can also save "pinned links", plan things into Google Calendar, use an AI
helper, and install a Chrome extension for reminders.

## Stack (don't change it without asking the owner)

- Python 3.14 + **Flask** (server-side pages with Jinja templates)
- **Microsoft SQL Server Express** (`localhost\SQLEXPRESS`, database `SubTrack`),
  reached with SQLAlchemy + pyodbc. Tests and quick runs use a SQLite file instead.
- Plain HTML + CSS (`app/static/style.css`) + small vanilla JavaScript files.
  **No** React/Vue/Tailwind/npm build step.
- Runs on the owner's Windows PC, published on his domain through Cloudflare Tunnel.
- Email: Resend. AI helper: Gemini API (free tier).

## Where things are

| Path | What |
|---|---|
| `app/__init__.py` | Creates the app, registers pages, `flask check-db` command |
| `app/config.py` | Reads `.env`, picks SQL Server or SQLite |
| `app/models.py` | Database tables as Python classes |
| `app/auth.py` | Sign up / log in / log out, confirm email, reset password |
| `app/security.py`, `app/validation.py` | CSRF, real visitor IP, rate limits, safe redirects; username/password rules |
| `app/mailer.py`, `app/tokens.py` | Sending email (Resend / file / test); one-time email links |
| `docs/CONTRACT.md` | **Routes and form field names the UI may rely on** |
| `app/subscriptions.py` | Subscription pages |
| `app/schedule.py`, `app/reminders.py` | Renewal date rules; the `flask send-reminders` job |
| `app/dashboard.py`, `app/settings.py` | Dashboard (+ JSON) and reminder settings |
| `app/subby.py`, `app/ai_providers.py` | Help bot endpoint; which AI model answers (Gemini / Phi / fake) |
| `app/links.py`, `app/link_preview.py` | Pinned links + automatic page titles |
| `app/admin.py` | Admin user list |
| `app/templates/` | HTML pages |
| `database/01_schema.sql` | **T-SQL schema: the source of truth for SQL Server** |
| `tests/` | Automated tests (pytest) |
| `docs/PROGRESS.md` | Plan + work log. **Read it first, update it last.** |
| `run_local.bat` / `run_tests.bat` | Start the site / run the tests |

## Who owns which files (lanes)

Two AIs may work at the same time **only if they are in different lanes**.

| Lane | Files | Who |
|---|---|---|
| **Backend** | `app/*.py`, `database/`, `tests/`, `requirements.txt`, `.env.example` | Claude, Codex |
| **UI** | `app/templates/`, `app/static/` (CSS, JS, images) | Antigravity (from Gemini's designs) |
| **PC setup** | `.bat` files, `deploy/`, Windows services, Cloudflare Tunnel, Task Scheduler | Codex (auto-start on boot: Antigravity) |
| **Extension** | `extension/` | Codex |

- UI work must not change Python, routes or form field `name=`s. If the UI needs
  new data from the server, write it in `docs/PROGRESS.md` under "Requests" for the backend lane.
- Designs from **Stitch** (via its MCP server) come as HTML using Tailwind.
  Don't paste that in: rebuild it with Jinja templates + classes in `style.css`,
  keep the existing form fields and routes, and save the mockup image in `docs/design/`.
- Backend work that needs a new page adds a **plain, working template**;
  the UI lane makes it pretty later.
- `AGENTS.md` and `docs/PROGRESS.md` can be edited by anyone; keep edits small.

## How to work here

1. **Check before you start.** Run `git status`. If there are uncommitted
   changes **in your lane** that you didn't make, stop and ask the owner.
2. Read `docs/PROGRESS.md` to see what's done and what's next.
3. Make the change. Keep it small and focused on what was asked.
4. Run the tests: `run_tests.bat` (or `.venv\Scripts\python -m pytest -q`).
   They must pass. Add or update tests for anything you add or change.
5. Add one line to the log in `docs/PROGRESS.md`: date, which AI you are, what changed.
6. Commit, starting the message with your name:
   `git commit -m "[codex] Add dashboard monthly total"`.
   The commit is the save point: if something breaks later, it can be undone.

## Rules that must never be broken

- **Never commit `.env`**, passwords, API keys or tokens (including the Stitch API key —
  MCP servers are set up in each tool's own user settings, never in this folder). Never print their values.
  New settings go in `.env.example` with a placeholder value.
- **Every database query for user data filters by the logged-in user**
  (`filter_by(user_id=current_user.id)`), so nobody can see someone else's data.
- **No SQL built by joining strings.** Use SQLAlchemy, or parameters (`:name`) in raw SQL.
- **Never DROP or TRUNCATE tables, or delete user data**, in code or SQL scripts.
- Database changes: add a **new numbered script** (`database/02_...sql`) that is
  safe to run twice (`IF NOT EXISTS ...`), **and** update `app/models.py` to match.
  Don't rewrite `01_schema.sql` in ways that would change existing tables.
- Links the user saves must be `http`/`https` only. Any code where the server
  fetches a URL goes through `app/link_preview.py`'s safety checks
  (public addresses only), never a plain `requests.get` on user input.
- Templates: never use `|safe` on user content.
- Don't add new packages without a good reason. Pin the version in
  `requirements.txt` and say why in the commit.
- Don't edit files outside this folder. The bug screenshots folder is read-only.

## Code style

- Clear names, short functions, comments that explain *why*, in plain English.
- Match the look in `DESIGN.md` (v2): violet buttons, lilac page, Plus Jakarta Sans,
  colours as variables in `style.css` `:root`. Pages must work at phone width (390px).
- User-facing text is friendly and short. Show errors with `flash(...)`.
- Windows paths and `.bat`/PowerShell commands in instructions (the owner uses Windows).

## Bug screenshots

The owner puts screenshots of problems or ideas in
`C:\Users\buith\Projects\Bug_Fix_image\`. The **file name describes the issue**
(e.g. `auto_know_what_link.png` = "make the app work out what a link is").
When asked to "check the bug folder", look at the newest image first.
