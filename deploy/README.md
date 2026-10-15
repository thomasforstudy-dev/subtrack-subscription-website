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
| `status.bat` | Double-click anytime to check if the tasks, port 8000, and domain are healthy. |
| `install_tasks.ps1` | The underlying PowerShell script called by `install_autostart.bat`. |
| `uninstall_tasks.ps1` | The underlying PowerShell script called by `uninstall_autostart.bat`. |
| `status.ps1` | The underlying PowerShell script called by `status.bat`. |

## Interview Explanation Cheat-Sheet

If asked in an interview:
> *"How do you host SubTrack on your PC reliably?"*
> 
> "Instead of running a debug server in an open command window, I use Waitress as a multi-threaded production WSGI server behind Cloudflare Tunnel for end-to-end HTTPS without exposing home ports. To ensure 24/7 uptime across PC restarts, I configured Windows Task Scheduler tasks triggered `AtStartup` running under `SYSTEM`. This gives a clean headless daemon that starts before user logon, never hits the 72-hour Task Scheduler timeout, and automatically restarts if interrupted."
