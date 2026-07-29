# Start the Agent Hub dashboard (Next.js dev server on http://localhost:3000)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root "frontend")
try {
    if (-not (Test-Path "node_modules")) {
        Write-Error "node_modules not found. Run .\scripts\setup.ps1 first."
    }
    npm run dev
} finally {
    Pop-Location
}
