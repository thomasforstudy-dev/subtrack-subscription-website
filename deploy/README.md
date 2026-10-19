# SubTrack Auto-Start on Boot (Production Deployment)

This directory sets up SubTrack to start automatically in the background whenever Windows boots, even before any user logs in.

## How it works

When Windows boots, two tasks in **Windows Task Scheduler** are automatically triggered:

1. **`SubTrack-Server`**
   - **Command**: `.venv\Scripts\python.exe serve.py`
   - **What it does**: Runs Waitress (a production-grade WSGI web server) listening on `http://127.0.0.1:8000`.
   - **Account**: `NT AUTHORITY\SYSTEM` (runs in background Session 0 with no command prompt popups).

2. **`SubTrack-Tunnel`**
   - **Command**: `cloudflared tunnel --no-autoupdate run --url http://127.0.0.1:8000 subtrack`
   - **What it does**: Establishes an encrypted Cloudflare Tunnel that forwards public web traffic from `https://alloutdeepclean.com` directly to `127.0.0.1:8000`.
   - **Account**: `NT AUTHORITY\SYSTEM` (uses credentials copied to `C:\Windows\System32\config\systemprofile\.cloudflared`).

## Key Production Reliability Settings

Both tasks are configured with production resilience settings:
- **`AtStartup` trigger**: Starts when the PC powers on, even before someone enters their Windows password.
- **Unlimited Execution Time (`ExecutionTimeLimit = 0`)**: Windows Task Scheduler defaults to stopping tasks after 72 hours. Setting this to 0 prevents Windows from killing the server after 3 days.
- **Auto-Restart on Crash (`RestartCount = 3`, `RestartInterval = 1m`)**: If either process crashes, Task Scheduler restarts it automatically.
- **Battery & Power (`AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries`)**: Prevents Windows from stopping the server if power fluctuates or runs on laptop battery.

## Files

| File | What it does |
|---|---|
| `install_autostart.bat` | Right-click -> "Run as administrator" to register and start both tasks. |
| `uninstall_autostart.bat` | Right-click -> "Run as administrator" to stop and remove both tasks. |
| `update_server.bat` | Right-click -> Run as administrator on the home PC: back up, update to the newest `main`, test, restart. |
| `status.bat` | Double-click anytime to check if the tasks, port 8000, and domain are healthy. |
| `install_tasks.ps1` | The underlying PowerShell script called by `install_autostart.bat`. |
| `uninstall_tasks.ps1` | The underlying PowerShell script called by `uninstall_autostart.bat`. |
| `status.ps1` | The underlying PowerShell script called by `status.bat`. |

## Interview Explanation Cheat-Sheet

If asked in an interview:
> *"How do you host SubTrack on your PC reliably?"*
> 
> "Instead of running a debug server in an open command window, I use Waitress as a multi-threaded production WSGI server behind Cloudflare Tunnel for end-to-end HTTPS without exposing home ports. To ensure 24/7 uptime across PC restarts, I configured Windows Task Scheduler tasks triggered `AtStartup` running under `SYSTEM`. This gives a clean headless daemon that starts before user logon, never hits the 72-hour Task Scheduler timeout, and automatically restarts if interrupted."

## Moving the live site to the home PC, and updating it

The live site and its database run on **one** PC: the home PC. The laptop is for
development only. Never run `SubTrack-Tunnel` on both machines at once: Cloudflare
would send some visitors to each PC, and each has its own database.

### First time on the home PC (skip what's already done)

1. Get the code: `git clone https://github.com/thomasforstudy-dev/subtrack-subscription-website.git C:\Users\buith\Projects\subtrack`
   (or `git pull` if the folder exists), then run `run_local.bat` once to build `.venv`.
2. Copy `.env` from the laptop **by USB stick or by typing it**, never by email, chat or GitHub.
   It must have a long random `SECRET_KEY` (the live site refuses to start with a weak one)
   and **no** `APP_ENV=development` line. Check `SITE_URL=https://alloutdeepclean.com`.
3. Email (Resend): in resend.com add the domain `alloutdeepclean.com`, put the DNS
   records it shows into Cloudflare, wait for "Verified", create an API key with
   "Sending access", then add to `.env` on the home PC:
   ```
   RESEND_API_KEY=re_...your key...
   MAIL_FROM=SubTrack <reminders@alloutdeepclean.com>
   ```
4. Cloudflare Tunnel login files: copy `C:\Users\buith\.cloudflared` from the machine
   that created the `subtrack` tunnel. Then right-click `install_autostart.bat` →
   Run as administrator.
5. Make yourself admin (nobody becomes admin by signing up any more):
   `.venv\Scripts\python -m flask --app app make-admin your-email@example.com`

### Every update (after `main` changes on GitHub)

Right-click `update_server.bat` → **Run as administrator**. It stops the site, backs up
`instance\` (SQLite database + uploaded bills) to `%USERPROFILE%\SubTrack-backups\`,
pulls `main`, installs packages, runs the tests and starts the site again. If the tests
fail it goes back to the version that was running. Old SQLite files get their new
columns automatically when the site starts.

**SQL Server instead of SQLite** (`DB_SERVER` set in `.env`): before updating, back up the
`SubTrack` database in SSMS, then run the `database\0N_*.sql` scripts you haven't run yet,
in number order. Each one is safe to run twice.

The reminder email job is **not** switched on by updating. Turning it on is a separate step
(Task Scheduler, `flask send-reminders`) after a test email to your own address works.
