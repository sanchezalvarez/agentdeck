# Agent Deck - fresh-PC bootstrap.
#
# This is the ONE step that cannot live in the dashboard: the dashboard is a
# Python backend + a Node frontend, so Python and Node must exist before it can
# run at all. This script installs whatever is missing (via winget, built into
# Windows 11), then hands off to setup.ps1.
#
# Runs under Windows PowerShell 5.1 too (a fresh PC has no pwsh yet), so this
# file stays ASCII-only and 5.1-compatible.
#
# Run it once on a new PC via agent-deck.bat in the repository root (choose
# "Install", or pass it as an argument), or directly:
#
#     powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
#
# Idempotent: anything already present is left alone.
$ErrorActionPreference = "Stop"

# Winget package ids. NodeJS.LTS currently resolves to Node 20+, which is what
# the project needs; Python.Python.3.12 pins the 3.12 line; Microsoft.PowerShell
# is PowerShell 7, needed by start-all.ps1 (it spawns "Start-Process pwsh").
$PYTHON_PACKAGE = "Python.Python.3.12"
$NODE_PACKAGE = "OpenJS.NodeJS.LTS"
$PWSH_PACKAGE = "Microsoft.PowerShell"

Write-Host "=== Agent Deck bootstrap ===" -ForegroundColor Cyan

function Test-OnPath {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-RealPython {
    # On Windows 11, "python" with no real Python installed resolves to a
    # Microsoft Store stub under WindowsApps that just opens the Store. Treat
    # that as "not installed" so we actually install Python.
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { return $false }
    if ($cmd.Source -like "*\WindowsApps\*") { return $false }
    return $true
}

function Update-SessionPath {
    # winget writes the new tool onto the machine/user PATH in the registry, but
    # the change is invisible to this already-running process. Re-read both
    # scopes so tools installed just now are found without opening a new shell.
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

function Install-WingetPackage {
    param([string]$Id)
    # $ErrorActionPreference=Stop does not trap native exit codes, so a failed
    # winget is caught by the post-install verification below, not here.
    winget install --id $Id --exact --silent `
        --accept-package-agreements --accept-source-agreements
    Update-SessionPath
}

if (-not (Test-OnPath "winget")) {
    Write-Error @"
winget was not found. It ships with Windows 11 but may be missing on older
builds. Install "App Installer" from the Microsoft Store, then re-run this
script. (Alternatively install Python 3.12+, Node 20+ and PowerShell 7
manually and run scripts\setup.ps1.)
"@
}

# --- Python ---------------------------------------------------------------
if (Test-RealPython) {
    Write-Host "Python already present: $((python --version) 2>&1)" -ForegroundColor Green
} else {
    Write-Host "Installing Python ($PYTHON_PACKAGE) via winget..." -ForegroundColor Cyan
    Install-WingetPackage $PYTHON_PACKAGE
}

# --- Node -----------------------------------------------------------------
if (Test-OnPath "node") {
    Write-Host "Node already present: $((node --version) 2>&1)" -ForegroundColor Green
} else {
    Write-Host "Installing Node.js ($NODE_PACKAGE) via winget..." -ForegroundColor Cyan
    Install-WingetPackage $NODE_PACKAGE
}

# --- PowerShell 7 ---------------------------------------------------------
if (Test-OnPath "pwsh") {
    Write-Host "PowerShell 7 already present: $((pwsh --version) 2>&1)" -ForegroundColor Green
} else {
    Write-Host "Installing PowerShell 7 ($PWSH_PACKAGE) via winget..." -ForegroundColor Cyan
    Install-WingetPackage $PWSH_PACKAGE
}

# --- Verify the tools are reachable now -----------------------------------
$missing = @()
if (-not (Test-RealPython)) { $missing += "python" }
if (-not (Test-OnPath "node")) { $missing += "node" }
if ($missing.Count -gt 0) {
    Write-Warning @"
$($missing -join ' and ') was installed but is not visible in this window yet.
Close this window, open a new terminal, and run:  .\scripts\setup.ps1
(Windows sometimes needs a fresh shell to pick up a new PATH entry.)
"@
    return
}

# --- Hand off to the normal setup -----------------------------------------
# setup.ps1 runs in this same process, so it inherits the PATH refreshed above.
Write-Host "`nPrerequisites ready - running setup..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "setup.ps1")

Write-Host @"

=== Bootstrap complete ===
Next: install OpenACP itself - start Agent Deck (agent-deck.bat start) and use the
"Install OpenACP" button on the dashboard's OpenACP page, then apply your
settings bundle and configure the OpenACP workspace.
"@ -ForegroundColor Green
