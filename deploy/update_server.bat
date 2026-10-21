@echo off
REM Run only in the live main checkout as Administrator, after the release gate.
REM SQL Server needs a separately verified database backup; instance contains uploads.
setlocal
cd /d "%~dp0.." || (
    echo Update FAILED at step: Open project folder.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Update FAILED at step: Locate Python virtual environment.
    echo Run run_local.bat once first.
    exit /b 1
)
".venv\Scripts\python.exe" -m deploy.update
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
