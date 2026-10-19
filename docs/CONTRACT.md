# SubTrack — route, form and JSON contract

What the backend promises the UI lane (Antigravity) and the extension/calendar
lane (Codex). **Field `name=`s and routes here must not change without updating
this file and keeping the old name working.** Owner of this file: backend lane.

Last change: 2026-10-19 — Claude — accounts (section A).

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
