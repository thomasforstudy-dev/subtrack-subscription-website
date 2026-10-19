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
- Claude/backend: review `docs/reviews/2026-10-19-quality-baseline.md` (R1–R8); strict expected-failure tests reproduce admin bootstrap, missing CSRF, invalid renewal date and signup-policy gaps. Coordinate CSRF/form and capability-copy changes with Antigravity.
- Claude/backend (from Antigravity UI lane):
  1. **Bills / OCR & Credit Card Statements**: Connect `#bill-review-form` (`subscriptions/_bills_section.html`) to backend OCR upload (`POST /bills/upload`, max 10 MB / 5 pages, PNG/JPG/WEBP/PDF) and confirmation (`POST /bills/<id>/confirm`), plus credit-card statement persistence for `#credit-cards`.
  2. **Gmail Invoice OAuth**: Separate OAuth scope/route (`/settings/gmail/connect` & `/settings/gmail/disconnect`) for `#settings` Gmail invoice reader (kept strictly separate from Google login).

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
- 2026-10-19 — Codex — On `codex/quality-baseline`, reviewed GitHub `af63951` (main only, no open PRs or Actions runs), prepared Windows/Ubuntu Python 3.14 CI, isolated tests from .env/external connections (including the dotenv 1.1.1 loader), and added subscription/user-isolation/config/reminder-log checks: 68 passed, 4 strict expected failures remain for Claude; findings/handoff in `docs/reviews/2026-10-19-quality-baseline.md`. SQL Server and hosted CI unverified; no push/deploy/training.
- 2026-10-19 — Antigravity — On `antigravity/ui-ux`, completed Sections 1–7 UI/UX overhaul (`landing.html/css/js`, `base.html`, `auth/*.html`, `subscriptions/*.html`, `links/*.html`, `_subby.html`, `subby.js`, `link-preview.js`, `app-ui.js`, `style.css`, `favicon.svg`, `icon-192.svg`, `manifest.webmanifest`), captured before/after synthetic viewport screenshots in `docs/design/`, and wrote handoff report `docs/reviews/2026-10-19-ui-ux-handoff.md` (68 passed, 4 xfailed).
- 2026-10-19 — Antigravity — On `antigravity/ui-ux`, reconciled UI templates and JS with Claude's backend contract (`c33f88d`, `docs/CONTRACT.md`): added `dashboard.html` and `settings.html`, wired `lead_days` + `manage_url` + full `form` preservation in `subscriptions/form.html`, replaced client-side float sums with server Decimal totals (`/dashboard` + `/dashboard.json`), wired server-side search/filter/sort/pagination/restore in `subscriptions/list.html`, added `provider`/`fallback` cloud-model notice in `subby.js`, added `favicon_url` (`referrerpolicy="no-referrer"`) in `links/list.html`, and formula-safe CSV export in `app-ui.js` (68 passed, 4 xfailed on baseline; 184/184 passed on combined overlay).

