# Stop OpenACP, whether it runs as a daemon or in the foreground.
#
# "openacp stop" only finds a daemonized instance: a foreground one writes no
# pid file and survives the call. This script covers both, and removes the
# cloudflared tunnel the CLI leaves behind either way.
#
# WARNING: this terminates running agent sessions.
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

$apiPort = if ($status -and $status.data.apiPort) { [int]$status.data.apiPort } else { 21420 }

if ($status -and $status.success -and $status.data.status -ne "offline") {
    # Graceful first: killing a daemon outright can leave a stale openacp.pid
    # behind and confuse the next start.
    $workspace = Split-Path $status.data.dir -Parent
    Write-Host "Stopping OpenACP daemon..." -ForegroundColor Cyan
    Push-Location $workspace
    try {
        openacp stop
    } finally {
        Pop-Location
    }
    Start-Sleep -Seconds 2
}

if (Test-Listening $apiPort) {
    # Still answering: a foreground instance the CLI could not see.
    Stop-OpenAcpNodeProcess -Label "foreground OpenACP"
    Start-Sleep -Seconds 1
}

& (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1") -All

if (Test-Listening $apiPort) {
    Write-Error "OpenACP is still listening on port $apiPort."
}

Write-Host "OpenACP stopped." -ForegroundColor Green
