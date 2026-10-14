@echo off
REM Run all automated tests. Every AI must see "passed" before committing.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run run_local.bat once first to set things up.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
".venv\Scripts\python.exe" -m pytest -q
pause
