@echo off
REM Run only in the live main checkout as Administrator, after the release gate.
REM SQL Server needs a separately verified database backup; instance contains uploads.
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing. Run run_local.bat once first.
    exit /b 1
)
".venv\Scripts\python.exe" -m deploy.update
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
