@echo off
REM ==========================================================================
REM  Update the live SubTrack site on THIS PC to the newest "main" from GitHub.
REM
REM  Run it on the server PC, in the live project folder, as Administrator
REM  (right-click > Run as administrator), because the SubTrack-Server task
REM  runs as SYSTEM:
REM      deploy\update_server.bat
REM
REM  What it does, in order (the site keeps running until step 5):
REM   1. stops if the folder has changes that aren't committed (never overwrites work)
REM   2. gets the newest main and installs the packages it needs
REM   3. runs the tests; if they fail, goes back to the old version and stops
REM   4. stops the site (SubTrack-Server task, and anything left on port 8000)
REM   5. copies instance\ (SQLite database + uploaded bills) to a backup folder
REM   6. checks the database (old SQLite files get their new columns here)
REM   7. starts the site again. The tunnel keeps running the whole time.
REM  Nothing is ever deleted. SQL Server users: back up the SubTrack database
REM  in SSMS first and run the new database\0N_*.sql scripts (see deploy\README.md).
REM ==========================================================================
setlocal
cd /d "%~dp0.."
set PY=.venv\Scripts\python.exe

if not exist "%PY%" (
    echo The virtual environment is missing. Run run_local.bat once first.
    exit /b 1
)

REM 1. Uncommitted changes? Then stop: someone is working in this folder.
git status --porcelain --untracked-files=no | findstr . >nul
if not errorlevel 1 (
    echo This folder has changes that are not committed. Commit or move them first.
    git status --short --untracked-files=no
    exit /b 1
)
for /f %%i in ('git rev-parse HEAD') do set OLD=%%i
echo Current version: %OLD%

REM 2. Newest main + packages (the running site is not touched yet).
git fetch origin || exit /b 1
git switch main || exit /b 1
git pull --ff-only origin main || exit /b 1
"%PY%" -m pip install -q -r requirements.txt || goto :rollback

REM 3. Tests must pass before the new version goes live. Their temporary files go
REM    to their own folder: run as Administrator, pytest's normal temp folder would
REM    belong to the admin account and break later test runs without admin.
"%PY%" -m pytest -q -p no:cacheprovider --basetemp "%TEMP%\subtrack-update-tests"
if errorlevel 1 goto :rollback

REM 4. Stop the site. The task's python can leave a child process holding
REM    port 8000, so stop whatever still listens there too.
schtasks /End /TN "SubTrack-Server" >nul 2>&1
timeout /t 3 /nobreak >nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:8000 .*LISTENING"') do taskkill /F /PID %%p >nul 2>&1

REM 5. Back up instance\ while nothing is writing to it (copies only).
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set STAMP=%%i
set BACKUP=%USERPROFILE%\SubTrack-backups\%STAMP%
robocopy instance "%BACKUP%" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
    echo Backup failed. Going back to the old version, the database was not changed.
    goto :rollback
)
echo Backup saved in %BACKUP%

REM 6. Database check. This also adds new columns to an old SQLite file.
"%PY%" -m flask --app app check-db
goto :restart

:rollback
echo.
echo The new version did not pass its checks. Going back to %OLD%.
REM --detach runs the old code without moving any branch; nothing is lost.
REM When the problem is fixed on GitHub, run this script again.
git switch --detach %OLD%
"%PY%" -m pip install -q -r requirements.txt

:restart
schtasks /Run /TN "SubTrack-Server" >nul
for /f %%i in ('git rev-parse --short HEAD') do echo Site started on version %%i. Check https://alloutdeepclean.com
endlocal
