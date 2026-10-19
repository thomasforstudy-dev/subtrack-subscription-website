# Release preparation — not activated

The integration preview uses synthetic SQLite data, fake AI and memory mail.
SQL Server tests use separate allowlisted databases. Neither proves that the
public site's running process uses SQL Server. Keep GOT-OCR and Phi training paused.

## Primary host and database

Owner must choose the primary Windows host and confirm its running service's
effective provider before release. Keep SQL Server as the intended relational
store. Do not set up a second writable copy on another device or migrate to
PostgreSQL/NoSQL for this milestone. Drive/Google One may hold encrypted backups;
they cannot host the live SQL database or an actively written SQLite file.

Record the chosen host, database name, schema revision and application commit
in a private operations record. Use `check-db` under the actual service identity.
Apply numbered migrations with a separate migration identity after backup and
review. The application identity needs only required data access; it must not
be sysadmin, create databases or change schema. Keep passwords outside Git.

## Private files and backup/restore rehearsal

Back up SQL data and `instance/uploads` together with a manifest of document
IDs, owner IDs, random stored names and hashes. Restrict backup/restore folders
to the operator and service accounts. Encrypt before offsite upload, keep the
recovery key separately, and set retention based on the owner's policy.

Before activation, perform a restore drill into a separately named test database
and private uploads directory with mail, AI and scheduled jobs disabled. Check
row counts, ownership, hashes, file downloads, bill/file associations and schema
readiness. Record restore time and recovery point; never overwrite the source.
This drill has **not** been performed by the integration test runner.

## Web process and privacy

Use production mode with a strong local secret, secure/HttpOnly/SameSite cookies
and HTTPS. Confirm proxy trust is restricted to the approved tunnel path; do not
trust forwarded identity headers from arbitrary clients. Keep uploads outside
static files. Test login/logout/CSRF and cross-account file/status access through
the actual HTTPS entry point before release. Never cache authenticated pages,
JSON, exports, bills or uploads in a service worker. PWA install/offline behavior
still requires browser review with Antigravity.

## Reminder activation — separate owner authorization

Do not install/enable a job or send email during integration. First review the
service account, working directory, environment, timezone and log permissions;
plan with `send-reminders --dry-run`. Verify verified-recipient/opt-out behavior,
stable payload/idempotency and overlapping-worker crash recovery. The owner must
approve the specific test recipient and live delivery before a send, then approve
the schedule separately. Record outcomes without copying recipient or key values
into shared artifacts.

## Monitoring and remaining prerequisites

Alert on failed jobs, retries/queue age, database connectivity, disk capacity,
private-file/manifest mismatch and backup age. Restrict/redact logs: no passwords,
tokens, invoice contents, connection strings or raw provider responses. Define
who receives alerts before enabling them. Review retention/deletion and recovery
procedures with the owner.

OCR verification waits for durable workers/adapters and field-source review.
Extension work waits for scoped, revocable token APIs. Real microphone/TTS,
Google import, production mail and backup restoration remain separate evidence.
Green CI does not authorize main merge, deployment, public exposure or training.

## Local review preview (PowerShell, from the isolated checkout)

```powershell
.\scripts\preview-control.ps1 start
.\scripts\preview-control.ps1 status
.\scripts\preview-control.ps1 stop
```

Default URL: http://127.0.0.1:8772. The helper starts a hidden loopback-only process
and stops only a matching saved script/port PID. Demo access is in the ignored
`instance/preview-access.json`. This URL belongs to this device; another computer
or phone needs its own preview or an explicitly approved private connection.
