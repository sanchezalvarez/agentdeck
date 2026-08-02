# Restart the OpenACP daemon.
#
# Needed after changing channel bindings in the dashboard — the Discord adapter
# reads its settings once at startup.
#
# WARNING: this terminates running agent sessions. Use -Force to skip the prompt.
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib.ps1")

$openacp = Get-Command openacp -ErrorAction SilentlyContinue
if (-not $openacp) {
    Write-Error "openacp not found on PATH."
}

$status = $null
try {
    $status = openacp status --json 2>$null | ConvertFrom-Json
} catch {
    $status = $null
}

# "openacp status" fails this way when .openacp/ has never been created —
# e.g. a genuinely fresh PC, or one where only the npm packages were
# installed. Fall back to the conventional workspace instead of aborting, the
# same way start-openacp.ps1 does.
$apiPort = 21420
if ($status -and $status.success -and $status.data.apiPort) { $apiPort = [int]$status.data.apiPort }

if ($status -and $status.success -and $status.data.dir) {
    # Foreground instances write no pid file — "openacp status" reports offline
    # even while one is running, so check the API port as well.
    $isRunning = ($status.data.status -ne "offline") -or (Test-Listening $apiPort)
    $workspace = Split-Path $status.data.dir -Parent
} else {
    $isRunning = Test-Listening $apiPort
    $workspace = Join-Path $HOME "openacp-workspace"
    if (-not (Test-Path $workspace)) {
        New-Item -ItemType Directory -Path $workspace | Out-Null
        Write-Host "[fix]   created OpenACP workspace folder: $workspace" -ForegroundColor Cyan
    }
}

if ($isRunning -and -not $Force) {
    Write-Host "OpenACP is running (status: $($status.data.status), pid: $($status.data.pid))." -ForegroundColor Yellow
    Write-Host "Restarting terminates any running agent sessions." -ForegroundColor Yellow
    $answer = Read-Host "Restart now? [y/N]"
    if ($answer -notmatch '^(y|yes)$') {
        Write-Host "Cancelled." -ForegroundColor Cyan
        return
    }
}

if ($isRunning) {
    Write-Host "Stopping OpenACP..." -ForegroundColor Cyan
    Push-Location $workspace
    try {
        openacp stop
    } finally {
        Pop-Location
    }
    Start-Sleep -Seconds 2

    # "openacp stop" cannot find a foreground instance (no pid file) — kill it
    # directly, otherwise the new window would run alongside the old one.
    if (Test-Listening $apiPort) {
        Stop-OpenAcpNodeProcess -Label "foreground OpenACP"
        Start-Sleep -Seconds 1
    }

    # The killed instance leaves its cloudflared tunnel behind.
    & (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1")
}

# "openacp restart" is deliberately not used: with runMode=foreground it would
# run inside this script's shell and die with it. A fresh window keeps the log
# visible and keeps OpenACP alive after this script exits.
Write-Host "Starting OpenACP in a new window..." -ForegroundColor Cyan
# Windows PowerShell when pwsh is absent — a PC that skipped the bootstrap has
# only the built-in one, and failing to start is worse than an older shell.
$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }
Start-Process $shell -ArgumentList "-NoExit", "-File", (Join-Path $PSScriptRoot "start-openacp.ps1")

Start-Sleep -Seconds 5
$after = openacp status --json 2>$null | ConvertFrom-Json
if ($after -and $after.success) {
    Write-Host "OpenACP status: $($after.data.status) (pid: $($after.data.pid))" -ForegroundColor Green
}
