# SubTrack — plan and work log

Deadline: **Sun 25 Oct 2026** (12 days from Wed 14 Oct).
Tick a box when the feature works **and** its tests pass.

## Plan

| Day | Date | Goal | Status |
|---|---|---|---|
| 1 | Wed 14 Oct | SQL Server ready, project on GitHub, app connects to SQL Server | 🟡 code done; owner still to run `01_schema.sql` and add `DB_` lines to `.env` |
| 2 | Thu 15 Oct | T-SQL schema + **Pinned links** (save, tag, search, pin, auto title) | ✅ |
| 3 | Fri 16 Oct | Go live on the domain: waitress + Cloudflare Tunnel, auto-start on boot | ⬜ |
| 4 | Sat 17 Oct | Email setup (Resend): confirm email at sign-up, forgot password | ⬜ |
| 5 | Sun 18 Oct | **Reminder emails**: daily job, no duplicates, renewal date moves forward | ⬜ |
| 6 | Mon 19 Oct | Dashboard: monthly spend, upcoming renewals, reminder banner, mobile | ⬜ |
| 7 | Tue 20 Oct | Plans + "Add to Google Calendar" buttons + calendar feed | ⬜ |
| 8 | Wed 21 Oct | **AI helper** (Gemini API) | ⬜ |
| 9 | Thu 22 Oct | **Chrome extension** (badge count + daily notification) | ⬜ |
| 10 | Fri 23 Oct | Security check, nightly backups, uptime monitor, privacy page | ⬜ |
| 11 | Sat 24 Oct | README with screenshots, demo account, demo video | ⬜ |
| 12 | Sun 25 Oct | Spare day for bugs | ⬜ |

## Who does what (suggested)

| Tool | Best at here |
|---|---|
| Claude | Lead: plan, backend, SQL Server / T-SQL, security, fixing bugs from screenshots, reviewing others' work |
| Antigravity | UI/UX: templates + CSS, checking pages in its browser |
| Codex | Clear, well-defined coding tasks and tests; second-opinion code review |
| Gemini | Research and explanations; Google parts (Calendar, Gemini API for the AI helper) |

## Log

Newest at the bottom. One line each: `date — tool — what changed`.

- 2026-10-14 — Claude — Switched app to SQL Server (Windows login), wrote `database/01_schema.sql` (tables, constraints, indexes, 2 views), added Pinned links, `flask check-db`, `run_local.bat`.
- 2026-10-14 — Claude — Links get their real page title automatically (`app/link_preview.py`, blocks private-network addresses). Added tests (`tests/`, `run_tests.bat`) and this shared AI rulebook (`AGENTS.md`).
