# SubTrack — plan and work log

Deadline: **Sun 25 Oct 2026** (12 days from Wed 14 Oct).
Tick a box when the feature works **and** its tests pass.

## Plan

| Day | Date | Goal | Status |
|---|---|---|---|
| 1 | Wed 14 Oct | SQL Server ready, project on GitHub, app connects to SQL Server | 🟡 code done; owner still to run `01_schema.sql` and add `DB_` lines to `.env` |
| 2 | Thu 15 Oct | T-SQL schema + **Pinned links** (save, tag, search, pin, auto title) | ✅ |
| 3 | Fri 16 Oct | Go live on the domain: waitress + Cloudflare Tunnel, auto-start on boot | ✅ live since 15 Oct; auto-start scripts in deploy/ |
| 4 | Sat 17 Oct | Email setup (Resend): confirm email at sign-up, forgot password | ⬜ |
| 5 | Sun 18 Oct | **Reminder emails**: daily job, no duplicates, renewal date moves forward | ⬜ |
| 6 | Mon 19 Oct | Dashboard: monthly spend, upcoming renewals, reminder banner, mobile | ⬜ |
| 7 | Tue 20 Oct | Plans + "Add to Google Calendar" buttons + calendar feed | ⬜ |
| 8 | Wed 21 Oct | **AI helper** (Gemini API) | 🟡 code done 15 Oct; owner to add `GEMINI_API_KEY` |
| 9 | Thu 22 Oct | **Chrome extension** (badge count + daily notification) | ⬜ |
| 10 | Fri 23 Oct | Security check, nightly backups, uptime monitor, privacy page | ⬜ |
| 11 | Sat 24 Oct | README with screenshots, demo account, demo video | ⬜ |
| 12 | Sun 25 Oct | Spare day for bugs | ⬜ |

## Who does what

| Tool | Role |
|---|---|
| **Claude** | Lead: backend features, SQL Server / T-SQL, security, reviews, bug fixes from screenshots |
| **Codex** | Runs things on the PC (setup, Cloudflare, services, backups), well-defined features, tests, reviews Claude's and Antigravity's work |
| **Gemini** (+ Stitch) | Designs the look: colour, fonts, page mockups. Doesn't edit the code |
| **Antigravity** | Turns Gemini's designs into the real templates + CSS; checks pages in its browser |

| Day | Backend lane | UI lane | PC setup / other |
|---|---|---|---|
| 1 | — | — | **Codex**: switch to SQL Server (run `01_schema.sql`, `.env`, `check-db`) |
| 2 | ✅ Claude: links | — | — |
| 3 | **Claude**: production server files | **Gemini** → design system + mockups | ✅ Claude: Cloudflare Tunnel · ✅ Antigravity: auto-start on boot |
| 4 | **Claude**: email (Resend), confirm email, forgot password | **Antigravity**: apply design to existing pages | Owner: Resend account + DNS in Cloudflare |
| 5 | **Claude**: reminder emails | **Antigravity**: landing page | **Codex**: daily reminder task in Task Scheduler |
| 6 | **Claude**: dashboard data | **Antigravity**: dashboard page | — |
| 7 | **Codex**: plans + Google Calendar buttons + feed | **Antigravity**: plans page | — |
| 8 | **Claude**: AI helper backend (Gemini API) | **Antigravity**: chat widget | — |
| 9 | **Claude**: API tokens for the extension | — | **Codex**: Chrome extension (`extension/`) |
| 10 | **Claude** + **Codex**: review each other's code (security) | **Antigravity**: mobile + accessibility check | **Codex**: nightly backups, uptime monitor |
| 11 | **Claude**: README | **Antigravity**: screenshots | **Gemini**: help script the demo video |
| 12 | Everyone: bug fixes from the bug folder | | |

## Requests

Things one lane needs from another. Delete a line when it's done.

- Backend lane (later): help bot "Subby" — Gemini answers, voice in/out (browser speech), hand-off to owner via Messenger/Zalo. Designs: `docs/design/subby-*.png`.
- UI lane (from Claude, 19 Oct): style the new account pages `auth/forgot.html`, `auth/reset.html`, `auth/verify.html`, the username field + password hint on sign up, "Forgot password?" on log in, the Log out button (now a small form in the top bar), and the `.verify-banner` "please confirm your email" form in `base.html`. Keep every `name=` and the `csrf_token` hidden field — see `docs/CONTRACT.md`.
- UI lane (from Claude, 19 Oct): `subby.js` built-in answers say "I email you before a renewal". Reminder emails aren't sent yet (section B), so soften that until they are.
- UI lane (from Claude, 19 Oct): style the new plain pages `dashboard.html` and `settings.html`, and the subscription list's search / filter / sort / pager and the new form fields (`lead_days`, `manage_url`). Fields and template variables: `docs/CONTRACT.md`.
- PC setup lane / Codex (from Claude, 19 Oct): Task Scheduler job running `.venv\Scripts\python -m flask --app app send-reminders` every 30 minutes, from the project folder, as the same account as SubTrack-Server. Log its output to a file. It's safe if two runs overlap.
- Owner: to really send email, add `RESEND_API_KEY` + `MAIL_FROM` (a verified Resend domain) to `.env`, then confirm your own email from the banner.
- UI lane (from Claude, 19 Oct): show `link.favicon_url` next to each pinned link (exact `<img>` attributes and the letter fallback are in `docs/CONTRACT.md` → Pinned links).

## Log

Newest at the bottom. One line each: `date — tool — what changed`.

- 2026-10-14 — Claude — Switched app to SQL Server (Windows login), wrote `database/01_schema.sql` (tables, constraints, indexes, 2 views), added Pinned links, `flask check-db`, `run_local.bat`.
- 2026-10-14 — Claude — Links get their real page title automatically (`app/link_preview.py`, blocks private-network addresses). Added tests (`tests/`, `run_tests.bat`) and this shared AI rulebook (`AGENTS.md`).
- 2026-10-14 — Claude — Added file lanes (AGENTS.md) and the day-by-day work split between Claude, Codex, Gemini and Antigravity (this file).
- 2026-10-15 — Claude — Wrote `DESIGN.md` (from `style.css`), linked Stitch project via `.stitch.json`, designed the 7-chapter scroll-story landing page for laptop 16:10, desktop 16:9 and phone 9:16. Mockups: `docs/design/landing-story-*.png`. No app code changed.
- 2026-10-15 — Claude — DESIGN.md v2 (colourful chaos→calm, Plus Jakarta Sans, Subby bot, scroll animation plan). New Stitch mockups: landing v2 (laptop/desktop/phone) + Subby chat and voice mode.
- 2026-10-15 — Claude — (owner asked Claude to do the UI lane this time) Built the animated landing page (`landing.html/css/js`), restyled every page to DESIGN.md v2, added Subby chat panel with pre-written answers (`_subby.html`, `subby.js`, Messenger/Zalo links from `.env`). Tests in `tests/test_pages.py`.
- 2026-10-15 — Claude — Site live at https://alloutdeepclean.com via Cloudflare Tunnel `subtrack` → waitress (`serve.py`, port 8000). Not auto-started yet: Antigravity to make serve.py + `cloudflared tunnel run subtrack` start on boot.
- 2026-10-15 — Claude — Subby hand-off shows only the contact apps set in .env (Messenger now; Zalo hidden). Next day: Subby's brain (Gemini), voice, hand-off messages.
- 2026-10-15 — Claude — Owner moved the auto-start-on-boot task from Codex to Antigravity. Added ponytail + scroll-craft skills to the repo (portfolio: shows which AI skills were used).
- 2026-10-15 — Antigravity — Created auto-start on boot Task Scheduler scripts and docs (deploy/install_autostart.bat, deploy/install_tasks.ps1, deploy/status.bat, deploy/uninstall_autostart.bat, deploy/README.md) for waitress and Cloudflare Tunnel.
- 2026-10-15 — Claude — Subby's brain: `app/subby.py` (`POST /subby/ask` → Gemini, key stays on server, 30 questions/hour per visitor, `[HANDOFF]` → Messenger card; browser falls back to built-in answers). Sign in with Google/GitHub (`app/oauth.py`, buttons appear once keys are in `.env`). Sign-up now has Confirm password. Tests: `test_auth.py`, `test_oauth.py`, `test_subby.py` (45 pass).
- 2026-10-15 — Claude — Fixed deploy scripts (admin prompt quoting in the .bat files, PowerShell 5.1 `(If ...)` error) and installed auto-start: SubTrack-Server + SubTrack-Tunnel run as SYSTEM at boot.
- 2026-10-15 — Claude — Gemini key created (project gen-lang-client-0817360794), backup model when Gemini is busy. Google sign-in uses new project subtrack-login-3365. Keys live in .env only.
- 2026-10-19 — codex — Archived 2,712 AAS skills in local skill-library/ (not activated; upstream clone Git-ignored), added Vietnamese guide and 19 skill recommendations for UI/UX, Python/PyTorch, backend/frontend and SQL; limited pytest discovery to application tests; 46 tests passed.
- 2026-10-19 — Claude — Accounts (branch `claude/accounts`): usernames, 12+ char passwords with upper/number/special, login by email or username with lockout, CSRF on every form, POST logout, safe `?next=`, confirm email + forgot/reset password (one-time hashed links, `app/tokens.py`), mail adapter (`app/mailer.py`: Resend with retries, file outbox, test memory), no more first-signup-is-admin (`flask make-admin`), production refuses a weak SECRET_KEY, HTTPS-only cookies, password change logs out other browsers, Subby trusts CF-Connecting-IP only from the tunnel. `database/02_accounts.sql` + automatic SQLite upgrade (`app/migrate.py`). Contract for UI: `docs/CONTRACT.md`. 111 tests pass (SQLite); 02 script NOT run on SQL Server (not reachable on this PC).
- 2026-10-19 — Claude — Reminders (branch `claude/reminders`, stacked on `claude/accounts`): subscriptions checked properly (Decimal money, 3-letter currency, dates, up to 3 lead times "14,7,3", manage link), list search/filter/sort/pages, restore; month-end + leap-year renewal rules (`app/schedule.py`); dashboard per currency (projected vs expected charges, mark paid/skipped) + `/dashboard.json`; settings (time zone, hour, on/off, channels); `flask send-reminders` job (roll dates with history, plan, claim, send with idempotency key, retry with back-off, crash recovery). `database/03_reminders.sql` + SQLite upgrade; new package `tzdata` (Windows has no time zones). 165 tests pass (SQLite); 03 script NOT run on SQL Server.
- 2026-10-19 — Claude — Links (branch `claude/links`, stacked on `claude/reminders`): link preview now connects to the exact address it checked (stops DNS rebinding), still checks HTTPS certificates; site icon from the page or `/favicon.ico` (no third-party icon service); same page saved twice is refused (`url_fingerprint`). `database/04_links.sql` + `flask fill-link-fingerprints`. 176 tests pass (SQLite); 04 script NOT run on SQL Server.
