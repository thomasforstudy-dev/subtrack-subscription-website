param(
    [ValidateSet('init','start','status','stop')][string]$Action = 'status',
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$sqlRoot = Split-Path -Parent $PSScriptRoot
$sqlInstance = Join-Path $sqlRoot 'instance'
$sqlScript = Join-Path $PSScriptRoot 'sql_preview.py'
$sqlPidFile = Join-Path $sqlInstance 'sql-preview.pid'
$sqlHealthUrl = 'http://127.0.0.1:8773/__sql_preview__/health'
New-Item -ItemType Directory -Force -Path $sqlInstance | Out-Null
if (!$Python) {
    $Python = Join-Path (Split-Path -Parent $sqlRoot) 'subtrack\.venv\Scripts\python.exe'
}
if (!(Test-Path -LiteralPath $Python)) { throw 'Pass -Python with a Python 3.14 virtual environment path.' }
if ($Action -eq 'init') {
    & $Python $sqlScript init
    exit $LASTEXITCODE
}
$sqlProcess = $null
if (Test-Path -LiteralPath $sqlPidFile) {
    $sqlProcessId = [int](Get-Content -LiteralPath $sqlPidFile)
    $sqlProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$sqlProcessId"
    if ($sqlProcess -and (!$sqlProcess.CommandLine.Contains($sqlScript) -or
        !$sqlProcess.CommandLine.Contains('serve'))) {
        throw 'Saved PID belongs to another process; refusing to control it.'
    }
}
if ($Action -eq 'stop') {
    if ($sqlProcess) {
        # Windows virtual-environment Python may launch a separate serving child.
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($sqlProcess.ProcessId)" |
            Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine.Contains($sqlScript) -and $_.CommandLine.Contains('serve') } |
            ForEach-Object { Stop-Process -Id $_.ProcessId }
        Stop-Process -Id $sqlProcess.ProcessId -ErrorAction SilentlyContinue
    }
    Write-Output 'Only this SQL development preview is stopped.'
    exit 0
}
if ($Action -eq 'start' -and !$sqlProcess) {
    $sqlListener = Get-NetTCPConnection -State Listen -LocalPort 8773 -ErrorAction SilentlyContinue
    if ($sqlListener) { throw 'Port 8773 is occupied; no existing process was stopped.' }
    $sqlProcess = Start-Process -FilePath $Python -ArgumentList @('-u', "`"$sqlScript`"", 'serve') `
        -WorkingDirectory $sqlRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $sqlInstance 'sql-preview.log') `
        -RedirectStandardError (Join-Path $sqlInstance 'sql-preview-error.log')
    $sqlProcess.Id | Set-Content -LiteralPath $sqlPidFile
}
if (!$sqlProcess) { Write-Output 'SQL preview is not running.'; exit 1 }
$sqlOwnedId = if ($sqlProcess.ProcessId) { $sqlProcess.ProcessId } else { $sqlProcess.Id }
$sqlDeadline = (Get-Date).AddSeconds(30)
do {
    try {
        $sqlHealth = Invoke-RestMethod -Uri $sqlHealthUrl -TimeoutSec 2
        $sqlAccess = Get-Content (Join-Path $sqlInstance 'sql-preview-access.json') -Raw | ConvertFrom-Json
        if ($sqlHealth.provider -ne 'mssql' -or $sqlHealth.database -ne 'SubTrack_CodexPreview_20261020' -or
            $sqlHealth.instance_id -ne $sqlAccess.instance_id) {
            throw 'Preview identity does not match the owned process.'
        }
        if ($sqlHealth.pid -ne $sqlOwnedId) {
            $sqlServingChild = Get-CimInstance Win32_Process -Filter "ProcessId=$($sqlHealth.pid)"
            if (!$sqlServingChild -or $sqlServingChild.ParentProcessId -ne $sqlOwnedId -or
                !$sqlServingChild.CommandLine.Contains($sqlScript) -or !$sqlServingChild.CommandLine.Contains('serve')) {
                throw 'Health PID is not this preview launcher or its serving child.'
            }
            $sqlHealth.pid | Set-Content -LiteralPath $sqlPidFile
        }
        Write-Output "Ready: http://127.0.0.1:8773/bills/ | SQL Server | $($sqlHealth.database) | $($sqlHealth.revision)"
        Write-Output 'Owner-only synthetic logins: instance\sql-preview-access.json'
        exit 0
    } catch {
        if ($Action -eq 'status') { Write-Output 'SQL preview failed its database/identity health check.'; exit 1 }
        if (!(Get-Process -Id $sqlOwnedId -ErrorAction SilentlyContinue)) {
            throw 'SQL preview exited; no SQLite fallback. Read instance\sql-preview-error.log.'
        }
        Start-Sleep -Milliseconds 400
    }
} while ((Get-Date) -lt $sqlDeadline)
throw 'SQL preview did not become healthy within 30 seconds; startup was not successful.'
