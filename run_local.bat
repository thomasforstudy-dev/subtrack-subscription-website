@echo off
REM ============================================================
REM  SubTrack - start the website on this PC (localhost)
REM  Double-click this file. Close the window to stop the site.
REM ============================================================
title SubTrack (local) - close this window to stop
cd /d "%~dp0"

REM 1. Make the virtual environment the first time
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo ERROR: Could not find Python. Install it from python.org
        echo and tick "Add python.exe to PATH" during install.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment found.
)

REM 2. Install / update packages
echo [2/4] Installing packages (first time takes a minute)...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Installing packages failed. Copy the red text above and send it to Claude.
    pause
    exit /b 1
)

REM 3. Make a .env settings file if there isn't one (uses the local test database).
REM    APP_ENV=development: without it the app acts as the live site and only
REM    sends login cookies over HTTPS, so logging in on http://127.0.0.1 fails.
if not exist ".env" (
    echo [3/4] Creating .env with a random secret key...
    ".venv\Scripts\python.exe" -c "import secrets; open('.env','w').write('SECRET_KEY='+secrets.token_hex(32)+'\nAPP_ENV=development\nDB_SERVER=\n')"
) else (
    echo [3/4] .env found.
)
".venv\Scripts\python.exe" -m flask --app app check-db

REM 4. Start the site and open the browser
echo [4/4] Starting SubTrack at http://127.0.0.1:5000
echo       Keep this window open. Close it to stop the site.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
".venv\Scripts\python.exe" -m flask --app app run --debug

echo.
echo SubTrack stopped.
pause
