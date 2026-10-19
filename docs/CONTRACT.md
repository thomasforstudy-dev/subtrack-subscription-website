# SubTrack — route, form and JSON contract

What the backend promises the UI lane (Antigravity) and the extension/calendar
lane (Codex). **Field `name=`s and routes here must not change without updating
this file and keeping the old name working.** Owner of this file: backend lane.

Last change: 2026-10-19 — Claude — accounts (section A); subscriptions, dashboard, settings, reminders (section B); link icons + duplicates (section C).

## Rules for every form

| Rule | Detail |
|---|---|
| CSRF | Every `method="post"` form must contain `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. Without it the server answers **400**. |
| JavaScript `fetch` POSTs | Send header `X-CSRF-Token` with the value of `<meta name="csrf-token">` (in `base.html`). |
| Exempt | `POST /subby/ask` only (JSON-only, touches no account data). |
| Errors | Shown with `flash()`; the page re-renders with the typed values kept (never the passwords). |
| `next` | Login keeps `?next=/some/page` in the URL. A form with no `action` posts back to the same URL, so it is kept automatically. Only same-site paths are followed. |

## Accounts

### Sign up — `GET/POST /register` (template `auth/register.html`)

| Field | Required | Rule (server checks; the UI may hint with the same rule) |
|---|---|---|
| `username` | yes | 3–30 characters: `a-z`, `0-9`, `_`. Upper case is turned into lower case. HTML hint: `pattern="[A-Za-z0-9_]{3,30}"` |
| `email` | yes | A normal email address, max 255 characters. Stored in lower case. |
| `password` | yes | **12–128 characters, at least one upper-case letter, one number and one special character** (anything that isn't a letter or number). HTML hint: `minlength="12" maxlength="128"` |
| `confirm` | yes | Must equal `password`. |

Success: logs in, sends a "confirm your email" link, redirects to `/subscriptions/`.

### Log in — `GET/POST /login` (template `auth/login.html`)

| Field | Required | Note |
|---|---|---|
| `identifier` | yes | Email **or** username. The old field name `email` still works. |
| `password` | yes | |

After 5 wrong tries for the same account from the same address in 15 minutes
(or 30 from one address), the page answers **429** with a "wait 15 minutes" message.

### Log out — `POST /logout`

Now **POST only** (a plain link answers 405). Use a small form:
`<form method="post" action="{{ url_for('auth.logout') }}">` + `csrf_token` + a button.

### Confirm email

| Route | Fields | Template |
|---|---|---|
| `GET /verify-email/<token>` | — | `auth/verify.html` (gets `valid: bool`) shows a "Confirm my email" button |
| `POST /verify-email/<token>` | `csrf_token` | — (redirects) |
| `POST /verify-email/resend` (logged in) | `csrf_token` | — (redirects back) |

The link is valid for 24 hours and works once. Clicking only *opens* the page;
the button press confirms, so email scanners that open links can't use it up.

### Forgot / reset password

| Route | Fields | Template |
|---|---|---|
| `GET/POST /forgot-password` | `email` | `auth/forgot.html` |
| `GET/POST /reset-password/<token>` | `password`, `confirm` (same rules as sign up) | `auth/reset.html` |

`/forgot-password` always shows the same message whether or not the account
exists. Reset links last 30 minutes, work once, and changing the password logs
the account out everywhere else.

### Values templates can use

| Name | Type | Meaning |
|---|---|---|
| `csrf_token()` | function | The token for the hidden field / meta tag |
| `current_user.username` | str | Shown in the top bar |
| `current_user.email_verified` | bool | `False` → show the "please confirm your email" banner with the resend button |
| `current_user.is_admin` | bool | Unchanged |

## Subscriptions

### Add / edit — `GET/POST /subscriptions/new`, `GET/POST /subscriptions/<id>/edit` (template `subscriptions/form.html`)

| Field | Required | Rule |
|---|---|---|
| `name` | yes | 1–120 characters |
| `amount` | no (0) | Decimal, dot for decimals, max 2 decimals, 0 – 99,999,999.99 |
| `currency` | no (USD) | 3 letters (`USD`, `EUR`, `VND`); stored upper case |
| `cycle` | yes | `weekly`, `monthly`, `yearly` |
| `next_renewal_at` | yes | `YYYY-MM-DD`, year 2000–2100 |
| `lead_days` | no (7) | Up to 3 numbers 0–365, comma separated: `14, 7, 3`. Old field `remind_days` (one number) still works. |
| `manage_url` | no | http/https link to manage or cancel; shown with `rel="noopener noreferrer nofollow"` |
| `notes` | no | Up to 2000 characters |

On an error the template gets `form` (what was typed) as well as `item`.

### List — `GET /subscriptions/` (template `subscriptions/list.html`)

Query string: `q` (searches name + notes), `status` = `active` (default) / `archived` / `all`,
`sort` = `renewal` (default) / `name` / `amount`, `page` (20 per page).
Template gets `items`, `pages` (Flask-SQLAlchemy pagination: `page`, `pages`,
`has_prev`, `prev_num`, `has_next`, `next_num`), `q`, `status`, `sort`, `today` (user's local date).

| Route | Fields |
|---|---|
| `POST /subscriptions/<id>/archive` | `csrf_token` |
| `POST /subscriptions/<id>/restore` | `csrf_token` |
| `POST /subscriptions/renewals/<renewal_id>` | `csrf_token`, `status` = `paid` / `skipped` / `expected` |

## Dashboard — `GET /dashboard` (template `dashboard.html`)

Template gets `today`, `totals` (list of `{currency, count, monthly, yearly}` —
one row per currency, never added together), `upcoming` (active subscriptions
renewing in the next 30 days), `expected` (passed renewal dates in the last 60
days, status `expected` / `paid` / `skipped`), `names` (subscription id → name).

"Projected" = what subscriptions *should* cost. "Expected charges" = dates that
passed; **not** proof of payment. "Actual spending" will come from confirmed bills.

### `GET /dashboard.json` (logged in; for the extension / calendar)

```json
{
  "today": "2026-10-19",
  "projected": [{"currency": "USD", "count": 2, "monthly": "20.00", "yearly": "240.00"}],
  "upcoming": [{"id": 3, "name": "Netflix", "amount": "9.99", "currency": "USD",
                "cycle": "monthly", "next_renewal_at": "2026-10-24", "days_left": 5,
                "manage_url": "https://netflix.com/cancel"}]
}
```

Money is a **string** (no float rounding), dates are ISO `YYYY-MM-DD`, missing
values are `null`. For now it uses the login cookie; the extension will get
API tokens later (backend lane).

## Settings — `GET/POST /settings` (template `settings.html`)

| Field | Rule |
|---|---|
| `timezone` | An IANA name like `Asia/Ho_Chi_Minh` (template gets `zones`, the full list) |
| `reminders_enabled` | checkbox `on` = reminders on; missing = off |
| `reminder_hour` | 0–23, the user's local time |
| `channels` | repeated checkbox; only `email` exists now (template gets `channels`) |

## Reminder job (PC setup lane)

```
.venv\Scripts\python -m flask --app app send-reminders          (send what is due)
.venv\Scripts\python -m flask --app app send-reminders --dry-run (plan only)
```

Safe to run every 15–60 minutes and twice at once. Prints counts. Exits with an
error if email isn't set up (rows stay waiting). Only confirmed emails get reminders.

## Pinned links

Routes and field names are unchanged (`url`, `title`, `tags`, `notes`, `is_pinned`, `form`).

| New | Detail |
|---|---|
| `link.favicon_url` | The site's **own** icon (from its `<link rel="icon">`, else `https://<site>/favicon.ico`). Show it with `<img src="{{ link.favicon_url }}" alt="" width="16" height="16" loading="lazy" referrerpolicy="no-referrer">` and a letter fallback when it fails. Never use a third-party favicon service (it would learn every saved link). Note: showing it lets the saved site see the viewer's IP, like opening the link. |
| Duplicates | Saving the same page twice (ignoring http/https, `www.`, trailing `/`, `#...`, `utm_*` and similar) is refused with a flash: "You already saved this link as “…”." |
| `POST /links/preview` | JSON now may include `"icon"` next to `"title"`, `"site_name"`, `"description"`. Send `X-CSRF-Token`. |

External links keep `target="_blank" rel="noopener noreferrer"`. Never `|safe` on titles or notes.

## Subby — `POST /subby/ask` (JSON, no CSRF token needed)

Request: `{"question": "...", "fun": true, "history": [{"role": "user"|"bot", "text": "..."}]}`

| Status | Body | Page should |
|---|---|---|
| 200 | `{"answer", "handoff": bool, "provider": "gemini"/"phi"/"fake", "fallback": bool}` | Show the answer. **If `fallback` is true, add a small note: "answered by a cloud model".** |
| 429 | `{"answer": "...slow down...", "handoff": false}` | Show it |
| 502 | `{"answer": null, "reason": "model-offline"/"model-failed"/"empty", "provider"}` | Use the built-in answers |
| 503 | `{"answer": null, "reason": "not-set-up"}` | Use the built-in answers |

## Admin

Nobody becomes admin by signing up any more. On the server PC:

```
.venv\Scripts\python -m flask --app app make-admin you@example.com
.venv\Scripts\python -m flask --app app make-admin you@example.com --remove
```

Removing the last admin is refused.

## Settings (`.env`)

| Name | Meaning |
|---|---|
| `APP_ENV` | `production` (default) or `development`. Production refuses to start without a real `SECRET_KEY` (32+ characters) and only sends cookies over HTTPS. |
| `TRUSTED_PROXIES` | Addresses allowed to tell us the visitor's real IP (Cloudflare Tunnel runs on this PC). Default `127.0.0.1,::1`. |
| `MAIL_BACKEND` | `resend`, `file` (saves emails in `instance/outbox/`), `memory` (tests) or `none`. Default: `resend` if `RESEND_API_KEY` is set, `file` in development, otherwise `none`. |
| `RESEND_API_KEY`, `MAIL_FROM`, `MAIL_REPLY_TO` | Real sending through Resend. |
| `DEFAULT_TIMEZONE` | Time zone for new accounts, e.g. `Asia/Ho_Chi_Minh` (default `UTC`). |
