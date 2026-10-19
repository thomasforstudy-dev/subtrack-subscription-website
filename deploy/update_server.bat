@echo off
REM ==========================================================================
REM  Update the live SubTrack site on THIS PC to the newest "main" from GitHub.
REM
REM  Run it on the server PC (the home PC), from the project folder, as
REM  Administrator (right-click > Run as administrator), because the
REM  SubTrack-Server task runs as SYSTEM:
REM      deploy\update_server.bat
REM
REM  What it does, in order:
REM   1. stops if the folder has changes that aren't committed (never overwrites work)
REM   2. stops the site (SubTrack-Server task) so the database file isn't in use
REM   3. copies instance\ (SQLite database + uploaded bills) to a backup folder
REM   4. gets the newest main, installs the packages it needs
REM   5. runs the tests; if they fail, goes back to the old version
REM   6. checks the database and starts the site again
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

REM 2. Stop the site.
schtasks /End /TN "SubTrack-Server" >nul 2>&1

REM 3. Back up instance\ (copies only).
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set STAMP=%%i
set BACKUP=%USERPROFILE%\SubTrack-backups\%STAMP%
robocopy instance "%BACKUP%" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 (
    echo Backup failed, so nothing was changed. Starting the old site again.
    schtasks /Run /TN "SubTrack-Server" >nul
    exit /b 1
)
echo Backup saved in %BACKUP%

REM 4. Newest main + packages.
git fetch origin || goto :restart
git switch main || goto :restart
git pull --ff-only origin main || goto :restart
"%PY%" -m pip install -q -r requirements.txt || goto :rollback

REM 5. Tests must pass before the new version goes live.
"%PY%" -m pytest -q
if errorlevel 1 goto :rollback

REM 6. Database check, then start.
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
