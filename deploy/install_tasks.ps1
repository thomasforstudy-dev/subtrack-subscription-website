<#
.SYNOPSIS
    Installs SubTrack web server and Cloudflare Tunnel as Windows Task Scheduler
    startup tasks that run automatically when the PC boots up.

.DESCRIPTION
    Creates two scheduled tasks under NT AUTHORITY\SYSTEM:
      1. SubTrack-Server: Waitress serving the Flask app on 127.0.0.1:8000
      2. SubTrack-Tunnel: Cloudflare Tunnel routing traffic from alloutdeepclean.com
         to 127.0.0.1:8000

    Both tasks:
      - Trigger: At system startup (before anyone logs in)
      - Run under SYSTEM account (no password required, runs in background)
      - Restart on failure (3 retries, 1 minute delay)
      - Never time out (ExecutionTimeLimit = 0)
      - Run on AC and battery power
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Ensure script is running with Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator. Please right-click PowerShell or install_autostart.bat and choose 'Run as administrator'."
    exit 1
}

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$servePy = Join-Path $projectRoot "serve.py"
$cloudflaredExe = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SubTrack - Setup Auto-Start on Boot" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"
Write-Host "Python:       $pythonExe"
Write-Host "Server entry: $servePy"
Write-Host "Cloudflared:  $cloudflaredExe"
Write-Host ""

# Verify prerequisites
if (-not (Test-Path $pythonExe)) {
    Write-Error "Virtual environment python.exe not found at: $pythonExe`nPlease run run_local.bat once to build the virtual environment."
    exit 1
}
if (-not (Test-Path $servePy)) {
    Write-Error "serve.py not found at: $servePy"
    exit 1
}
if (-not (Test-Path $cloudflaredExe)) {
    # Check PATH if not at default location
    $cfInPath = (Get-Command "cloudflared.exe" -ErrorAction SilentlyContinue)
    if ($cfInPath) {
        $cloudflaredExe = $cfInPath.Source
        Write-Host "Found cloudflared in PATH: $cloudflaredExe" -ForegroundColor Green
    } else {
        Write-Error "cloudflared.exe not found at $cloudflaredExe or in PATH."
        exit 1
    }
}

# 1. Ensure Cloudflare credentials are in SYSTEM profile so SYSTEM account can run the tunnel
$userCloudflared = "C:\Users\buith\.cloudflared"
$systemCloudflared = "C:\Windows\System32\config\systemprofile\.cloudflared"

if (Test-Path $userCloudflared) {
    Write-Host "[1/4] Copying Cloudflare tunnel credentials to SYSTEM profile..." -ForegroundColor Yellow
    if (-not (Test-Path $systemCloudflared)) {
        New-Item -ItemType Directory -Path $systemCloudflared -Force | Out-Null
    }
    Copy-Item -Path "$userCloudflared\*" -Destination $systemCloudflared -Recurse -Force
    Write-Host "      Credentials copied to: $systemCloudflared" -ForegroundColor Green
} else {
    Write-Warning "User cloudflared folder not found at: $userCloudflared"
}

# Common task settings for 24/7 background servers
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -Priority 4

$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$systemPrincipal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# 2. Register SubTrack-Server task
Write-Host "[2/4] Registering Task: SubTrack-Server..." -ForegroundColor Yellow
$serverAction = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "serve.py" `
    -WorkingDirectory $projectRoot

Register-ScheduledTask `
    -TaskName "SubTrack-Server" `
    -Description "SubTrack production web server (Waitress) on port 8000" `
    -Action $serverAction `
    -Trigger $startupTrigger `
    -Settings $taskSettings `
    -Principal $systemPrincipal `
    -Force | Out-Null

Write-Host "      Task 'SubTrack-Server' registered successfully." -ForegroundColor Green

# 3. Register SubTrack-Tunnel task
Write-Host "[3/4] Registering Task: SubTrack-Tunnel..." -ForegroundColor Yellow
$tunnelAction = New-ScheduledTaskAction `
    -Execute $cloudflaredExe `
    -Argument "tunnel --no-autoupdate run --url http://127.0.0.1:8000 subtrack" `
    -WorkingDirectory $projectRoot

Register-ScheduledTask `
    -TaskName "SubTrack-Tunnel" `
    -Description "Cloudflare Tunnel routing alloutdeepclean.com to SubTrack port 8000" `
    -Action $tunnelAction `
    -Trigger $startupTrigger `
    -Settings $taskSettings `
    -Principal $systemPrincipal `
    -Force | Out-Null

Write-Host "      Task 'SubTrack-Tunnel' registered successfully." -ForegroundColor Green

# 4. Start both tasks immediately
Write-Host "[4/4] Starting tasks now..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName "SubTrack-Server"
Start-ScheduledTask -TaskName "SubTrack-Tunnel"
Start-Sleep -Seconds 3

# Check status
$serverTask = Get-ScheduledTask -TaskName "SubTrack-Server"
$tunnelTask = Get-ScheduledTask -TaskName "SubTrack-Tunnel"

Write-Host ""
Write-Host "Status Summary:" -ForegroundColor Cyan
Write-Host "  SubTrack-Server: $($serverTask.State)" -ForegroundColor (If ($serverTask.State -eq 'Running') { 'Green' } Else { 'Yellow' })
Write-Host "  SubTrack-Tunnel: $($tunnelTask.State)" -ForegroundColor (If ($tunnelTask.State -eq 'Running') { 'Green' } Else { 'Yellow' })

# Test local endpoint
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000" -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  Local server test: HTTP 200 OK (http://127.0.0.1:8000)" -ForegroundColor Green
    } else {
        Write-Host "  Local server test: HTTP $($response.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Warning "Local server test failed: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Auto-start installation complete! The site will now start automatically when Windows boots." -ForegroundColor Green
