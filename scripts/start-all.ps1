# Start the Agent Deck backend, the dashboard and the OpenACP daemon.
#
# Anything already running is left untouched — re-running this script is safe
# and will not produce "port already in use" errors.
#
# Note: starting OpenACP from here is a desktop convenience. The Agent Deck
# backend itself still never starts or stops OpenACP (see README).
param(
    [switch]$NoBrowser,
    # Report what would be started without starting anything.
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib.ps1")

function Wait-ForPort {
    param([int]$Port, [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Listening $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

$backendPort = [int](Get-EnvValue "AGENT_DECK_PORT" "8765")
$frontendPort = 3000

Write-Host "Agent Deck launcher" -ForegroundColor Cyan
Write-Host "------------------"

# --- Backend --------------------------------------------------------------
if (Test-Listening $backendPort) {
    Write-Host "[skip]  Backend already running on port $backendPort" -ForegroundColor Yellow
} else {
    Write-Host "[start] Backend (migrations + FastAPI on port $backendPort)" -ForegroundColor Green
    if (-not $DryRun) {
        Start-Process pwsh -ArgumentList "-NoExit", "-File", (Join-Path $root "scripts\start-backend.ps1")
    }
}

# --- Dashboard ------------------------------------------------------------
if (Test-Listening $frontendPort) {
    Write-Host "[skip]  Dashboard already running on port $frontendPort" -ForegroundColor Yellow
} else {
    Write-Host "[start] Dashboard (Next.js on port $frontendPort)" -ForegroundColor Green
    if (-not $DryRun) {
        Start-Process pwsh -ArgumentList "-NoExit", "-File", (Join-Path $root "scripts\start-frontend.ps1")
    }
}

# --- OpenACP --------------------------------------------------------------
# Even when OpenACP is already running, previous runs may have leaked
# orphaned cloudflared tunnels — clean those up first.
if (-not $DryRun) {
    & (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1")
}

$openacp = Get-Command openacp -ErrorAction SilentlyContinue
if (-not $openacp) {
    Write-Host "[warn]  openacp not found on PATH — start it yourself" -ForegroundColor Yellow
} else {
    $status = $null
    try {
        $status = openacp status --json 2>$null | ConvertFrom-Json
    } catch {
        $status = $null
    }

    $openacpPort = 21420
    if ($status -and $status.success -and $status.data.apiPort) { $openacpPort = [int]$status.data.apiPort }

    if ($null -eq $status -or -not $status.success) {
        # "openacp status" fails this way on a genuinely fresh PC too: with no
        # ~/openacp-workspace yet, there is nothing for it to report on. That
        # used to just print a warning and stop here, silently skipping the
        # only thing that would actually fix it — start-openacp.ps1 now
        # creates the workspace itself, so attempt the same start a human
        # would do by hand next instead of leaving OpenACP off.
        if (Test-Listening $openacpPort) {
            Write-Host "[skip]  OpenACP already running in foreground (port $openacpPort)" -ForegroundColor Yellow
        } else {
            Write-Host "[start] OpenACP in its own window (status unavailable - likely first run on this PC)" -ForegroundColor Green
            if (-not $DryRun) {
                Start-Process pwsh -ArgumentList "-NoExit", "-File", (Join-Path $root "scripts\start-openacp.ps1")
            }
        }
    } elseif ($status.data.status -ne "offline") {
        Write-Host "[skip]  OpenACP already running (status: $($status.data.status), pid: $($status.data.pid))" -ForegroundColor Yellow
    } elseif (Test-Listening $openacpPort) {
        # Foreground instances write no pid file, so "openacp status" reports
        # offline even while one is running. Trusting the status here would
        # start a second instance — and a second cloudflared tunnel.
        Write-Host "[skip]  OpenACP already running in foreground (port $openacpPort)" -ForegroundColor Yellow
    } else {
        # Own window, foreground: the log stays visible and closing the window
        # stops OpenACP. Running it inline would block this launcher instead.
        $workspace = Split-Path $status.data.dir -Parent
        Write-Host "[start] OpenACP in its own window ($workspace)" -ForegroundColor Green
        if (-not $DryRun) {
            Start-Process pwsh -ArgumentList "-NoExit", "-File", (Join-Path $root "scripts\start-openacp.ps1")
        }
    }
}

# --- Wait and report ------------------------------------------------------
if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run — nothing was started." -ForegroundColor Cyan
    return
}

Write-Host ""
Write-Host "Waiting for services..." -ForegroundColor Cyan

$backendUp = Wait-ForPort -Port $backendPort
$frontendUp = Wait-ForPort -Port $frontendPort

Write-Host ""
if ($backendUp) {
    Write-Host "  API        http://127.0.0.1:$backendPort/api/health" -ForegroundColor Green
} else {
    Write-Host "  API        did not come up — check the backend window" -ForegroundColor Red
}
if ($frontendUp) {
    Write-Host "  Dashboard  http://localhost:$frontendPort" -ForegroundColor Green
} else {
    Write-Host "  Dashboard  did not come up — check the dashboard window" -ForegroundColor Red
}
Write-Host "  OpenACP    openacp status  |  openacp logs" -ForegroundColor Green

if ($frontendUp -and -not $NoBrowser) {
    Start-Process "http://localhost:$frontendPort"
}
