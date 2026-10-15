@echo off
REM ============================================================
REM  SubTrack - Uninstall Auto-Start Tasks
REM  Stops and removes SubTrack-Server and SubTrack-Tunnel from
REM  Windows Task Scheduler.
REM ============================================================
title SubTrack - Remove Auto-Start
cd /d "%~dp0"

REM Check for Administrator privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo  Administrator rights required.
    echo  Requesting elevation...
    echo ============================================================
    REM Re-open this same file as admin. Windows shows a Yes/No prompt.
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall_tasks.ps1"

echo.
pause
