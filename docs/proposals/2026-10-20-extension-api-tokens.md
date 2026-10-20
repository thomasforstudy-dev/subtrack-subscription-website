# Proposal: API tokens for the Chrome extension (to agree with Codex first)

Status: **draft contract, not implemented.** Claude builds the backend after Codex (extension
lane) agrees or changes this. Nothing here exists in the code yet.

## Why

The extension shows a badge ("2 renewals this week") and one daily notification. It must not
use the website's login cookie: a token the owner can see, limit and revoke is safer and
works from the extension's background script.

## Tokens (migration `08_api_tokens.sql` + model `ApiToken`)

| Column | Meaning |
|---|---|
| `user_id` | Owner (CASCADE from users) |
| `name` | Owner's label, e.g. "Chrome on laptop" (≤ 60) |
| `token_hash` | SHA-256 of the secret (unique). **The secret itself is never stored** |
| `prefix` | First 8 characters, to recognise it in the list |
| `scopes` | Comma list; first version only `renewals:read` |
| `created_at`, `last_used_at`, `expires_at`, `revoked_at` | Expiry 90 days by default, at most 365 |

Secret format: `st_` + 32 random URL-safe bytes. Shown **once** when created.

## Owner pages (website, cookie login + CSRF)

| Route | What |
|---|---|
| `GET /settings/tokens` | List: name, prefix, scopes, created, last used, expires, revoked |
| `POST /settings/tokens` | `name`, `days` (1–365), `scopes` → shows the secret once |
| `POST /settings/tokens/<id>/revoke` | Revoke now (kept in the list, never deleted) |

At most 5 active tokens per account.

## Extension API (token only, no cookies)

`Authorization: Bearer st_…`. Requests with only a session cookie get 401: the API never
uses cookies, so it needs no CSRF token and can't be triggered by another website.

| Route | Scope | Answer |
|---|---|---|
| `GET /api/v1/renewals?days=7` (1–31) | `renewals:read` | `{"today", "timezone", "items": [{"id", "name", "amount": "9.99", "currency", "next_renewal_at", "days_left", "manage_url"}]}`, the owner's active subscriptions only |
| `GET /api/v1/me` | any | `{"username", "timezone", "scopes", "expires_at"}` |

Errors: `401 {"error": "missing-token" | "bad-token" | "expired" | "revoked"}`,
`403 {"error": "missing-scope"}`, `429 {"error": "slow-down"}`.

Limits: 120 requests per hour per token; 20 failed token checks per 10 minutes per IP.
CORS: only the extension's origin from `.env` `EXTENSION_ORIGIN=chrome-extension://<id>`.
`last_used_at` updated at most once per minute (no write on every request).

## Tests planned

Secret shown once and only its hash stored; wrong/expired/revoked/missing → 401 with no data;
scope missing → 403; another user's subscriptions never returned; cookie-only request → 401;
rate limits; revoke takes effect immediately; token list shows prefixes only; SQLite + the
synthetic SQL Server database.

## Questions for Codex

1. The extension ID / origin for CORS, and how often it polls (proposed: every 6 hours + on browser start).
2. Store the secret in `chrome.storage.local` (survives restarts) or `chrome.storage.session`?
3. Any scope needed beyond `renewals:read` (for example `links:read`) for the first version?
4. Badge counts: renewals within 7 days, or the owner's lead time per subscription?
