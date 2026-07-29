# Rembrosoft Agent Hub — one-time setup
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== Rembrosoft Agent Hub setup ===" -ForegroundColor Cyan

# 1. Verify prerequisites
try {
    $pythonVersion = (python --version) 2>&1
    Write-Host "Python: $pythonVersion"
} catch {
    Write-Error "Python was not found on PATH. Install Python 3.12+ from https://www.python.org/downloads/"
}
try {
    $nodeVersion = (node --version) 2>&1
    Write-Host "Node:   $nodeVersion"
} catch {
    Write-Error "Node.js was not found on PATH. Install Node 20+ from https://nodejs.org/"
}

# 2. Backend virtual environment + dependencies
Write-Host "`n--- Backend ---" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")

# A .venv copied from another PC hard-codes that PC's Python home in
# pyvenv.cfg, so its python.exe cannot start here. Verify the interpreter
# actually runs; if not (or it is missing), rebuild it from scratch.
$venvPython = ".\.venv\Scripts\python.exe"
$venvOk = $false
if (Test-Path $venvPython) {
    & $venvPython --version *> $null
    $venvOk = ($LASTEXITCODE -eq 0)
    if (-not $venvOk) {
        Write-Host "Existing .venv is broken (likely copied from another PC) - rebuilding." -ForegroundColor Yellow
    }
}
if (-not $venvOk) {
    if (Test-Path ".venv") { Remove-Item -Recurse -Force ".venv" }
    python -m venv .venv
    Write-Host "Created backend\.venv"
}

& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt --quiet
Write-Host "Backend dependencies installed."
Pop-Location

# 3. CLI dependencies (installed into the backend venv for local test runs;
#    global installation is handled by install-agent-report.ps1)
Write-Host "`n--- CLI ---" -ForegroundColor Cyan
Push-Location (Join-Path $root "cli")
& (Join-Path $root "backend\.venv\Scripts\python.exe") -m pip install -r requirements.txt --quiet
Write-Host "CLI dependencies installed."
Pop-Location

# 4. Frontend dependencies
Write-Host "`n--- Frontend ---" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
npm install
Pop-Location

# 5. OpenACP channel bindings — dist/ is a build artifact and is not committed,
#    so a fresh clone has to compile it before the adapter hook can be applied.
Write-Host "`n--- OpenACP channel bindings ---" -ForegroundColor Cyan
Push-Location (Join-Path $root "openacp-channel-bindings")
npm install
npm run build
Write-Host "Channel bindings compiled to dist\."
Pop-Location

# 6. .env
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $root ".env.example") $envFile
    Write-Host "`nCreated .env from .env.example — review it and set AGENT_HUB_WRITE_TOKEN."
} else {
    Write-Host "`n.env already exists — not overwriting."
}

Write-Host @"

=== Setup complete ===
Next steps:
  1. Review .env (set AGENT_HUB_WRITE_TOKEN for authenticated writes).
  2. Start the backend:   .\scripts\start-backend.ps1
  3. Start the frontend:  .\scripts\start-frontend.ps1   (or .\scripts\start-all.ps1)
  4. Install the CLI:     .\scripts\install-agent-report.ps1
  5. Optional seed data:  cd backend; .\.venv\Scripts\python.exe -m app.seed
Dashboard: http://localhost:3000    API: http://127.0.0.1:8765/api/health
"@ -ForegroundColor Green
