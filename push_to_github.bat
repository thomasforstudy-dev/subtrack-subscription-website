@echo off
REM ============================================================
REM  SubTrack - upload (push) the project to GitHub
REM  Double-click this file. The first time, it asks for your
REM  GitHub repo link and opens a browser window to sign in.
REM ============================================================
title SubTrack - push to GitHub
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git is not installed or not on PATH. Install it from https://git-scm.com
    goto :fail
)

REM --- 1. Safety: never upload passwords/keys or users' data -------------
set "LEAK="
for /f "delims=" %%F in ('git ls-files .env instance') do set "LEAK=%%F"
if defined LEAK (
    echo.
    echo STOP: Git is tracking a private file: %LEAK%
    echo It holds secrets or user data and must not go to GitHub.
    echo Nothing was uploaded. Ask Claude to help remove it from Git history.
    goto :fail
)
echo [1/4] Safety check passed: .env and the database are not included.

REM --- 2. Save any changes that aren't committed yet ---------------------
git add -A
git diff --cached --quiet
if errorlevel 1 (
    git commit -q -m "Save work before pushing to GitHub"
    if errorlevel 1 (
        echo Could not commit. If Git asks who you are, run these once:
        echo   git config --global user.name "Your Name"
        echo   git config --global user.email "you@example.com"
        goto :fail
    )
    echo [2/4] Saved your latest changes in a new commit.
) else (
    echo [2/4] Everything was already committed.
)

REM --- 3. Use "main" as the branch name and connect to GitHub ------------
git branch -M main
git remote get-url origin >nul 2>nul
if not errorlevel 1 goto :push

echo.
echo [3/4] This project isn't connected to GitHub yet.
echo       1. Open https://github.com/new
echo       2. Repository name: subtrack
echo       3. Do NOT tick "Add a README", .gitignore or license (leave it empty)
echo       4. Click "Create repository" and copy the HTTPS link,
echo          like https://github.com/yourname/subtrack.git
echo.
:ask_url
set "REPO="
set /p "REPO=Paste the repo link here and press Enter: "
if not defined REPO goto :ask_url
echo %REPO% | findstr /b /i "https://github.com/" >nul
if errorlevel 1 (
    echo That should start with https://github.com/ - try again.
    goto :ask_url
)
git remote add origin "%REPO%"

:push
REM --- 4. Upload ----------------------------------------------------------
echo [4/4] Uploading to GitHub (a browser window may open to sign in)...
git push -u origin main
if errorlevel 1 (
    echo.
    echo Upload failed. Common reasons:
    echo  - "Repository not found": the link is wrong or the repo wasn't created.
    echo      Fix the link with:  git remote set-url origin https://github.com/yourname/subtrack.git
    echo  - "rejected ... fetch first": the GitHub repo isn't empty ^(it has a README^).
    echo      Delete it and create it again empty, or send the message to Claude.
    goto :fail
)

echo.
echo Done! Your code is on GitHub:
git remote get-url origin
echo Next time, just double-click this file again to upload new changes.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
