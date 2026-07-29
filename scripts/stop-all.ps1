# Stop the Agent Hub backend, the dashboard and the OpenACP daemon.
#
# Closing the console windows does not always terminate the processes they
# started, which leaves ports 3000/8765 occupied. This kills them properly.
#
# Only processes whose command line points at this repository (or at the
# OpenACP CLI) are touched — unrelated node/python processes are left alone.
param(
    [switch]$KeepOpenAcp
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib.ps1")
$self = $PID

Write-Host "Agent Hub — stopping services" -ForegroundColor Cyan
Write-Host "-----------------------------"

# --- OpenACP (graceful) ---------------------------------------------------
# Stopped via the CLI rather than Stop-Process: killing the daemon outright can
# leave a stale openacp.pid behind and confuse the next start.
if ($KeepOpenAcp) {
    Write-Host "[skip]  OpenACP left running (-KeepOpenAcp)" -ForegroundColor Yellow
} else {
    $openacp = Get-Command openacp -ErrorAction SilentlyContinue
    if (-not $openacp) {
        Write-Host "[skip]  openacp not on PATH" -ForegroundColor Yellow
    } else {
        $status = $null
        try { $status = openacp status --json 2>$null | ConvertFrom-Json } catch { $status = $null }

        if ($status -and $status.success -and $status.data.status -eq "offline") {
            Write-Host "[skip]  OpenACP already stopped" -ForegroundColor Yellow
        } else {
            Write-Host "[stop]  OpenACP daemon" -ForegroundColor Green
            openacp stop 2>&1 | ForEach-Object { "        $_" }
            Start-Sleep -Seconds 2
        }
    }
}

# --- Agent Hub processes --------------------------------------------------
$rootPattern = "*$root*"

$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $self -and $_.CommandLine -and (
        ($_.Name -in @("python.exe", "node.exe") -and $_.CommandLine -like $rootPattern) -or
        ($_.Name -eq "pwsh.exe" -and $_.CommandLine -like "*scripts\start-*")
    )
}

if (-not $targets) {
    Write-Host "[skip]  No backend or dashboard processes running" -ForegroundColor Yellow
} else {
    foreach ($target in $targets) {
        $label = switch -Wildcard ($target.CommandLine) {
            "*uvicorn*"      { "backend" }
            "*next*"         { "dashboard" }
            "*start-backend*"  { "backend window" }
            "*start-frontend*" { "dashboard window" }
            default          { $target.Name }
        }
        try {
            Stop-Process -Id $target.ProcessId -Force -ErrorAction Stop
            Write-Host "[stop]  $label (pid $($target.ProcessId))" -ForegroundColor Green
        } catch {
            Write-Host "[skip]  $label (pid $($target.ProcessId)) already gone" -ForegroundColor Yellow
        }
    }
}

# --- Leftover OpenACP node processes --------------------------------------
if (-not $KeepOpenAcp) {
    Stop-OpenAcpNodeProcess
}

# --- Leaked cloudflared tunnels -------------------------------------------
# The OpenACP CLI does not stop its cloudflared child when killed; with
# -KeepOpenAcp only orphans are removed, otherwise every OpenACP tunnel.
if ($KeepOpenAcp) {
    & (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1")
} else {
    & (Join-Path $PSScriptRoot "cleanup-openacp-tunnels.ps1") -All
}

# --- Verify ---------------------------------------------------------------
Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Ports:" -ForegroundColor Cyan
foreach ($port in @(3000, 8765, 21420)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "  $port still in use by pid $($conn.OwningProcess) ($($proc.ProcessName))" -ForegroundColor Red
    } else {
        Write-Host "  $port free" -ForegroundColor Green
    }
}
