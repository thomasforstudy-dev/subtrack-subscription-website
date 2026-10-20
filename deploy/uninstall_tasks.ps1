<#
.SYNOPSIS
    Stops and removes the SubTrack Windows Task Scheduler startup tasks.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Ensure script is running with Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator. Please right-click PowerShell or uninstall_autostart.bat and choose 'Run as administrator'."
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  SubTrack - Uninstall Auto-Start on Boot Tasks" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

foreach ($taskName in @("SubTrack-Tunnel", "SubTrack-Server", "SubTrack-Reminders")) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Stopping task: $taskName..." -ForegroundColor Yellow
        try {
            Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        } catch {}

        Write-Host "Removing task: $taskName..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed $taskName." -ForegroundColor Green
    } else {
        Write-Host "Task $taskName was not found." -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Auto-start tasks removed successfully." -ForegroundColor Green
