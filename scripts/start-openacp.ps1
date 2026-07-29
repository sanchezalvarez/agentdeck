# Run the OpenACP server in the foreground, in this window.
#
# Deliberately NOT a daemon: the log stays visible here, and closing this window
# stops OpenACP together with every running agent session.
#
# The server is started from its workspace so it resolves the existing .openacp
# folder instead of creating a new one in the current path.
$ErrorActionPreference = "Stop"

$openacp = Get-Command openacp -ErrorAction SilentlyContinue
if (-not $openacp) {
    Write-Error "openacp not found on PATH."
}

$workspace = $env:OPENACP_WORKSPACE
if (-not $workspace) {
    $status = $null
    try {
        $status = openacp status --json 2>$null | ConvertFrom-Json
    } catch {
        $status = $null
    }
    if ($status -and $status.success -and $status.data.dir) {
        $workspace = Split-Path $status.data.dir -Parent
    } else {
        $workspace = Join-Path $HOME "openacp-workspace"
    }
}

if (-not (Test-Path $workspace)) {
    Write-Error "OpenACP workspace not found: $workspace"
}

Write-Host "OpenACP  $workspace" -ForegroundColor Cyan
Write-Host "Close this window to stop OpenACP and all agent sessions." -ForegroundColor DarkGray
Write-Host ""

# Tunnels leaked by previous runs would pile up next to the one this run spawns.
& (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1")

Set-Location $workspace
# "--foreground" is the only way to keep the server in this window: plain
# "openacp start" always daemonizes, whatever runMode says in the config.
openacp --foreground
