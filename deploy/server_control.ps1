param(
    [ValidateSet('check', 'stop', 'start')][string]$Action,
    [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference = 'Stop'
try {
    $root = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\')
    $python = Join-Path $root '.venv\Scripts\python.exe'
    $task = Get-ScheduledTask -TaskName 'SubTrack-Server' -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1 -or $actions[0].Execute -ine $python -or
        $actions[0].WorkingDirectory.TrimEnd('\') -ine $root -or
        $actions[0].Arguments.Trim() -ine 'serve.py') {
        throw 'Server task does not belong to this checkout.'
    }
    $listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    $ownedIds = @()
    foreach ($listener in $listeners) {
        if ($listener.LocalAddress -ne '127.0.0.1') { throw 'Unexpected public listener on port 8000.' }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ParentProcessId)"
        $ownedPython = $process.ExecutablePath -ieq $python -or $parent.ExecutablePath -ieq $python
        if (-not $ownedPython -or $process.CommandLine -notmatch '(?i)(?:^|\s)"?serve\.py"?(?:\s|$)') {
            throw 'Port 8000 is held by an unrecognised process; it will not be stopped.'
        }
        $ownedIds += $process
    }
    if ($Action -eq 'stop') {
        Stop-ScheduledTask -TaskName 'SubTrack-Server' -ErrorAction Stop
        foreach ($owned in $ownedIds) {
            # Recheck creation time after stopping the task to protect against PID reuse.
            $remaining = Get-CimInstance Win32_Process -Filter "ProcessId=$($owned.ProcessId)"
            if ($remaining -and $remaining.CreationDate -eq $owned.CreationDate -and
                $remaining.CommandLine -eq $owned.CommandLine) {
                Stop-Process -Id $owned.ProcessId -ErrorAction Stop
            }
        }
        $deadline = (Get-Date).AddSeconds(10)
        while (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
            if ((Get-Date) -ge $deadline) { throw 'Server did not release port 8000 within ten seconds.' }
            Start-Sleep -Milliseconds 250
        }
    } elseif ($Action -eq 'start') {
        if ($listeners.Count) { throw 'Port 8000 is still occupied; startup refused.' }
        Start-ScheduledTask -TaskName 'SubTrack-Server' -ErrorAction Stop
    }
    exit 0
} catch {
    Write-Host ('Server control failed: ' + $_.Exception.Message)
    exit 1
}
