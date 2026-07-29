# Install the agent-report CLI so every agent can reach it.
#
# The package deliberately goes into the backend venv rather than Python's
# user-site (`pip install --user`, which this script used to do). Agent
# processes run with user-site disabled — OpenACP-spawned agents were seeing
#
#     ModuleNotFoundError: No module named 'agent_report'
#
# even though the command itself started, because PYTHONNOUSERSITE drops
# user-site from sys.path. A venv's own site-packages is immune to that.
#
# Only the generated launcher is copied onto PATH. It embeds the absolute path
# to the venv interpreter, so it resolves the package from any shell, any
# working directory and inside any other virtualenv. It is a real .exe rather
# than a .cmd shim on purpose: Git Bash — which agents commonly run commands
# through — does not resolve .cmd files from PATH.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib.ps1")

$cli = Join-Path $root "cli"
$python = Join-Path $root "backend\.venv\Scripts\python.exe"
$launcher = Join-Path $root "backend\.venv\Scripts\agent-report.exe"

if (-not (Test-Path $python)) {
    Write-Error "Backend venv not found. Run .\scripts\setup.ps1 first."
}

Write-Host "Installing agent-report into the backend venv..." -ForegroundColor Cyan
& $python -m pip install $cli --quiet
if ($LASTEXITCODE -ne 0) { Write-Error "pip install failed." }
if (-not (Test-Path $launcher)) { Write-Error "pip did not produce $launcher." }

# A leftover --user install would shadow the launcher below with the very copy
# that fails under PYTHONNOUSERSITE.
$systemPython = Get-Command python -ErrorAction SilentlyContinue
if ($systemPython) {
    & python -m pip uninstall -y agent-report 2>&1 | Out-Null
}

# Prefer a directory already on PATH: agents inherit PATH when they are spawned,
# so a brand-new directory would stay invisible to everything already running.
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$onPath = ($userPath -split ';' | Where-Object { $_ }) |
    Where-Object { $_ -like "*\Python*\Scripts" -and (Test-Path $_) } |
    Select-Object -First 1

if ($onPath) {
    $targetDir = $onPath
} else {
    $targetDir = Join-Path $root "bin"
    if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Path $targetDir | Out-Null }
    if ($userPath -notlike "*$targetDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$targetDir", "User")
        Write-Host "Added $targetDir to the user PATH — restart OpenACP so agents inherit it." -ForegroundColor Yellow
    }
    $env:Path = "$env:Path;$targetDir"
}

Copy-Item $launcher (Join-Path $targetDir "agent-report.exe") -Force
Write-Host "Launcher installed to: $targetDir"

Write-Host "`nVerifying (with user-site disabled, the way agents run):" -ForegroundColor Cyan
$previous = $env:PYTHONNOUSERSITE
$env:PYTHONNOUSERSITE = "1"
try {
    & (Join-Path $targetDir "agent-report.exe") --version
    if ($LASTEXITCODE -ne 0) { Write-Error "agent-report failed with user-site disabled." }
} finally {
    if ($null -eq $previous) { Remove-Item Env:PYTHONNOUSERSITE } else { $env:PYTHONNOUSERSITE = $previous }
}

Write-Host "`nagent-report is ready." -ForegroundColor Green
Write-Host "Re-run this script after rebuilding backend\.venv — the launcher points into it." -ForegroundColor DarkGray
