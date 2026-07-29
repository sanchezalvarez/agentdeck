# Start the Agent Deck backend (runs migrations first)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Backend venv not found. Run .\scripts\setup.ps1 first."
}

Push-Location $backend
try {
    Write-Host "Applying database migrations..." -ForegroundColor Cyan
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Alembic migration failed." }

    # Read host/port from .env if present, otherwise use defaults.
    $bindHost = "127.0.0.1"
    $bindPort = "8765"
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*AGENT_DECK_HOST\s*=\s*(.+)$') { $bindHost = $Matches[1].Trim() }
            if ($line -match '^\s*AGENT_DECK_PORT\s*=\s*(.+)$') { $bindPort = $Matches[1].Trim() }
        }
    }

    Write-Host "Starting FastAPI on http://${bindHost}:${bindPort} ..." -ForegroundColor Cyan
    & $python -m uvicorn app.main:app --host $bindHost --port $bindPort
} finally {
    Pop-Location
}
