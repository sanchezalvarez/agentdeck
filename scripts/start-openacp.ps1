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
    # A genuinely fresh PC has no workspace folder yet — nothing in setup.ps1 or
    # the OpenACP install step creates it, so without this the very first start
    # here would hard-fail before OpenACP gets a chance to bootstrap .openacp\.
    New-Item -ItemType Directory -Path $workspace | Out-Null
    Write-Host "[fix]   created OpenACP workspace folder: $workspace" -ForegroundColor Cyan
}

Write-Host "OpenACP  $workspace" -ForegroundColor Cyan
Write-Host "Close this window to stop OpenACP and all agent sessions." -ForegroundColor DarkGray
Write-Host ""

# --- Channel-bindings hook -------------------------------------------------
# Reinstalling or updating @openacp/discord-adapter restores its untouched dist
# and takes the hook with it. An unhooked adapter looks exactly like a healthy
# one until a Discord message fails to open a session, so repair it here instead
# of waiting for someone to notice and press Redeploy in the dashboard.
$bindingsDir = Join-Path (Split-Path -Parent $PSScriptRoot) "openacp-channel-bindings"
$hookScript = Join-Path $bindingsDir "scripts\install-hook.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[skip]  node not on PATH - channel-bindings hook not verified" -ForegroundColor Yellow
} elseif (-not (Test-Path $hookScript)) {
    Write-Host "[skip]  install-hook.mjs not found - channel-bindings hook not verified" -ForegroundColor Yellow
} elseif (-not (Test-Path (Join-Path $bindingsDir "dist\index.js"))) {
    Write-Host "[warn]  channel-bindings module not built - run 'npm run build' in $bindingsDir" -ForegroundColor Yellow
} else {
    node $hookScript --check 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[ok]    channel-bindings hook installed" -ForegroundColor DarkGray
    } else {
        Write-Host "[fix]   channel-bindings hook missing - installing it" -ForegroundColor Cyan
        node $hookScript 2>&1 | ForEach-Object { Write-Host "        $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn]  hook install failed - Discord channel bindings will NOT work" -ForegroundColor Red
        }
    }
    # A non-zero code from the check above is an answer, not this script's result.
    $global:LASTEXITCODE = 0
}

# Tunnels leaked by previous runs would pile up next to the one this run spawns.
& (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1")

Set-Location $workspace
# "--foreground" is the only way to keep the server in this window: plain
# "openacp start" always daemonizes, whatever runMode says in the config.
openacp --foreground
