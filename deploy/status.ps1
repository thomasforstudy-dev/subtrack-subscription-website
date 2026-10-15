<#
.SYNOPSIS
    Checks the status of the SubTrack background tasks, local port, and domain.
#>

[CmdletBinding()]
param()

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SubTrack - Service Status Check" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Scheduled Tasks Status
Write-Host "1. Windows Scheduled Tasks:" -ForegroundColor Yellow
foreach ($taskName in @("SubTrack-Server", "SubTrack-Tunnel")) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
        $color = if ($task.State -eq 'Running') { 'Green' } else { 'Yellow' }
        Write-Host "   - $taskName : $($task.State)" -ForegroundColor $color
        if ($info) {
            Write-Host "     Last Run:   $($info.LastRunTime) (Result: $($info.LastTaskResult))" -ForegroundColor Gray
            Write-Host "     Next Run:   $($info.NextRunTime)" -ForegroundColor Gray
        }
    } else {
        Write-Host "   - $taskName : NOT INSTALLED" -ForegroundColor Red
    }
}

Write-Host ""
# 2. Local Port 8000 Check
Write-Host "2. Local Waitress Server (http://127.0.0.1:8000):" -ForegroundColor Yellow
try {
    $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000" -UseBasicParsing -TimeoutSec 3
    if ($res.StatusCode -eq 200) {
        Write-Host "   [OK] Responding with HTTP 200" -ForegroundColor Green
    } else {
        Write-Host "   [!] Responding with HTTP $($res.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [X] Not reachable: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
# 3. Public Domain Check
Write-Host "3. Public Domain (https://alloutdeepclean.com):" -ForegroundColor Yellow
try {
    $res = Invoke-WebRequest -Uri "https://alloutdeepclean.com" -UseBasicParsing -TimeoutSec 5
    if ($res.StatusCode -eq 200) {
        Write-Host "   [OK] Live and reachable with HTTP 200 via Cloudflare Tunnel" -ForegroundColor Green
    } else {
        Write-Host "   [!] Responding with HTTP $($res.StatusCode)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [X] Not reachable: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
