@echo off
REM ============================================================
REM  SubTrack - Check Service Status
REM  Checks Task Scheduler tasks, port 8000, and public domain.
REM ============================================================
title SubTrack - Service Status
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0status.ps1"

echo.
pause
