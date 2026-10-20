@echo off
REM ============================================================
REM  AllOutFree - Run Scheduled Reminder Job
REM  Dispatches due renewal reminders and moves passed dates forward.
REM  Logs output to instance\reminders.log.
REM ============================================================
cd /d "%~dp0\.."
if not exist "instance" mkdir "instance"

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    if exist "..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\.venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
    if exist "..\..\.venv\Scripts\python.exe" set "PYTHON_EXE=..\..\.venv\Scripts\python.exe"
)

echo [%date% %time%] Running send-reminders... >> "instance\reminders.log"
"%PYTHON_EXE%" -m flask --app app send-reminders >> "instance\reminders.log" 2>&1
