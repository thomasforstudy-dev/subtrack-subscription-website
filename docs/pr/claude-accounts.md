# [claude] Accounts: usernames, strong passwords, CSRF, email confirm + reset, admin bootstrap

Branch: `claude/accounts` → `main` (draft, don't merge without the owner)

## Objective
Section A of the backend assignment: make accounts safe and complete before
reminders are built on top of them.

## What changed
- **Sign up** needs a unique username (3–30, `a-z 0-9 _`, NFKC + lower case) and a
  12–128 character password with an upper-case letter, a number and a special character.
- **Log in** with email *or* username. 5 wrong passwords per account+address
  (30 per address) in 15 minutes → 429 lockout. Same message for a wrong
  password and a missing account; a dummy hash check keeps the timing similar.
- **CSRF** token on every POST form and the link-preview `fetch`; only
  `/subby/ask` (JSON-only) is exempt. **Logout is POST.** `?next=` only goes to pages on this site.
- **Confirm email** (24 h) and **forgot/reset password** (30 min): one-time links,
  stored only as SHA-256 hashes, bound to the address they were sent to.
  `/forgot-password` answers the same for every email.
- **Mail adapter** `app/mailer.py`: Resend (10 s timeout, 3 tries with back-off
  on 429/5xx/network errors, `Idempotency-Key`), `file` outbox for this PC,
  `memory` for tests, `none` when not set up. The live site never claims to
  have sent an email it couldn't send.
- **Admin**: signing up never makes an admin. `flask make-admin <email|username>`
  (`--remove` refuses to remove the last admin). Existing admins keep their flag.
- **Sessions**: production (`APP_ENV` default) refuses a SECRET_KEY shorter than
  32 characters; cookies are HttpOnly, SameSite=Lax and HTTPS-only. The login
  cookie carries a password fingerprint, so changing/resetting the password
  logs out every other browser.
- **OAuth**: an unconfirmed password account with the same email is taken back
  by the verified Google/GitHub owner (its password is switched off), which stops
  an attacker from pre-registering someone else's email.
- **Subby**: rate limit uses `CF-Connecting-IP` only when the request comes from
  `TRUSTED_PROXIES` (default 127.0.0.1, ::1). FACTS no longer promise reminder
  emails that aren't sent yet.

## Schema
- `users.username` (unique, backfilled as `user_<id>`), `users.email_verified_at`
- new table `auth_tokens`
- SQL Server: `database/02_accounts.sql` (rerunnable, no DROP)
- SQLite (the live site today): added automatically at start-up by `app/migrate.py`

## How to deploy (owner)
1. Back up `instance\subtrack.db` (copy the file).
2. Merge, then restart the SubTrack-Server task. The SQLite file is upgraded on start.
3. Make sure `.env` has no `APP_ENV=development` on the live PC (the default is production).
4. Log in again (old login cookies stop working once) — your username is `user_1`.
5. Optional now, needed for emails: `RESEND_API_KEY` and `MAIL_FROM` in `.env`.
6. SQL Server later: run `01_schema.sql` then `02_accounts.sql` in SSMS.

## Tests actually run
- `pytest`: **111 passed** (SQLite, Python 3.14) — new: `test_auth.py`,
  `test_email_links.py`, `test_mailer.py`, `test_migrate.py`, `test_subscriptions.py`,
  extra cases in `test_oauth.py` and `test_subby.py`.
- Rehearsed on a **copy** of the live SQLite file in production mode with the real
  `.env`: starts, columns added, 1 user still admin, 2 subscriptions + 2 links kept,
  `/`, `/login`, `/register`, `/forgot-password` return 200.

## Not verified
- `database/02_accounts.sql` was **not run on SQL Server** (`localhost\SQLEXPRESS`
  wasn't reachable from this PC). SQLite tests say nothing about T-SQL.
- Real Resend delivery (no key yet); only faked in tests.
- `/forgot-password` sends the email inside the request, so an existing account
  answers a little slower than a missing one (timing). Fix later by sending
  through the reminder outbox/worker from section B.
- Rate limits live in memory: they reset on restart and assume one server process.
- Sign-up still says "That email is already registered" (normal UX, but it
  does reveal that an email has an account).

## UI lane (Antigravity)
See `docs/CONTRACT.md` and the Requests in `docs/PROGRESS.md`: style
`auth/forgot.html`, `auth/reset.html`, `auth/verify.html`, the username field,
the log-out form and the `.verify-banner`. Keep every `name=` and the `csrf_token` field.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
