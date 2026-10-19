param(
    [ValidateSet('start', 'stop', 'status')][string]$Action = 'status',
    [ValidateRange(1024, 65535)][int]$Port = 8772,
    [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$previewRoot = Split-Path -Parent $PSScriptRoot
$previewInstance = Join-Path $previewRoot 'instance'
New-Item -ItemType Directory -Force -Path $previewInstance | Out-Null
$previewPidFile = Join-Path $previewInstance "preview-$Port.pid"
$previewScript = Join-Path $PSScriptRoot 'preview.py'
$previewProcess = $null
if (Test-Path -LiteralPath $previewPidFile) {
    $previewProcessId = [int](Get-Content -LiteralPath $previewPidFile)
    $previewProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$previewProcessId"
    if ($previewProcess -and (!$previewProcess.CommandLine.Contains($previewScript) -or
        !$previewProcess.CommandLine.Contains("--port $Port"))) {
        throw 'Saved PID belongs to another process. Refusing to stop or replace it.'
    }
}
if ($Action -eq 'stop') {
    if ($previewProcess) { Stop-Process -Id $previewProcess.ProcessId }
    Write-Output 'This synthetic preview is stopped.'
    exit
}
if ($Action -eq 'start' -and !$previewProcess) {
    if (!$Python) {
        $Python = Join-Path $previewRoot '.venv\Scripts\python.exe'
        if (!(Test-Path -LiteralPath $Python)) {
            $Python = Join-Path (Split-Path -Parent $previewRoot) 'subtrack\.venv\Scripts\python.exe'
        }
    }
    if (!(Test-Path -LiteralPath $Python)) { throw 'Pass -Python with the Python 3.14 virtual environment path.' }
    $previewProcess = Start-Process -FilePath $Python -ArgumentList @('-u', "`"$previewScript`"", '--port', "$Port") `
        -WorkingDirectory $previewRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $previewInstance "preview-$Port.log") `
        -RedirectStandardError (Join-Path $previewInstance "preview-$Port-error.log")
    $previewProcess.Id | Set-Content -LiteralPath $previewPidFile
}
if ($previewProcess) {
    Write-Output "Synthetic SQLite preview: http://127.0.0.1:$Port (this device only)."
    Write-Output 'Demo login is in instance\preview-access.json; mail and AI are simulated.'
} else { Write-Output 'This preview is not running.' }
