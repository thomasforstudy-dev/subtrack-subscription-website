@echo off
REM ============================================================
REM  SubTrack - Install Auto-Start on Windows Boot
REM  Registers SubTrack Server (Waitress) and Cloudflare Tunnel
REM  in Windows Task Scheduler so they start automatically when
REM  the PC boots up (runs in background under SYSTEM account).
REM ============================================================
title SubTrack - Auto-Start Setup
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

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_tasks.ps1"

echo.
pause
