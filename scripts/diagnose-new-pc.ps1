# Read-only health check for a fresh-PC Agent Deck setup (see AGENTS.md "Moving to
# another PC"). Walks every precondition in the same order the setup path depends on
# them, so a broken chain shows exactly where it snaps instead of surfacing only as a
# downstream 503 from /api/openacp/channel-bindings.
#
# Never writes, installs or deletes anything. Safe to re-run any time.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

# Kept in sync manually with backend/app/services/openacp_install.py — bump both
# together when that file's CLI_VERSION / ADAPTER_VERSION change.
$PinnedCliVersion = "2026.518.2"
$PinnedAdapterVersion = "2026.518.1"

$script:FailCount = 0

function Write-Ok {
    param([string]$Message)
    Write-Host "[ok]    $Message" -ForegroundColor Green
}
function Write-Warn {
    param([string]$Message)
    Write-Host "[warn]  $Message" -ForegroundColor Yellow
}
function Write-Fail {
    param([string]$Message)
    Write-Host "[fail]  $Message" -ForegroundColor Red
    $script:FailCount++
}

Write-Host "=== Agent Deck / OpenACP fresh-PC diagnosis ===" -ForegroundColor Cyan

# --- Prerequisites ----------------------------------------------------------
Write-Host "`n--- Prerequisites ---" -ForegroundColor Cyan

if ($PSVersionTable.PSVersion.Major -ge 7) {
    Write-Ok "PowerShell $($PSVersionTable.PSVersion)"
} else {
    Write-Warn "PowerShell $($PSVersionTable.PSVersion) — Agent Deck scripts expect PowerShell 7+"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) { Write-Ok "python on PATH: $((python --version) 2>&1)" }
else { Write-Fail "python not on PATH — install Python 3.12+" }

$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) { Write-Ok "node on PATH: $(node --version)" }
else { Write-Fail "node not on PATH — install Node 20+" }

$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) { Write-Ok "npm on PATH: $(npm --version)" }
else { Write-Fail "npm not on PATH — install Node 20+" }

# --- Repo build artifacts ----------------------------------------------------
Write-Host "`n--- Repo build artifacts ---" -ForegroundColor Cyan

$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython --version *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok "backend\.venv works" }
    else { Write-Fail "backend\.venv exists but its python.exe won't run — likely copied from another PC. Delete backend\.venv and re-run scripts\setup.ps1" }
} else {
    Write-Fail "backend\.venv missing — run scripts\setup.ps1"
}

if (Test-Path (Join-Path $root "frontend\node_modules")) { Write-Ok "frontend\node_modules present" }
else { Write-Fail "frontend\node_modules missing — run scripts\setup.ps1" }

if (Test-Path (Join-Path $root "openacp-channel-bindings\dist\index.js")) { Write-Ok "openacp-channel-bindings\dist built" }
else { Write-Fail "openacp-channel-bindings\dist missing — cd openacp-channel-bindings; npm install; npm run build" }

if (Test-Path (Join-Path $root ".env")) { Write-Ok ".env present" }
else { Write-Fail ".env missing — run scripts\setup.ps1 (copies .env.example)" }

# --- OpenACP install ----------------------------------------------------------
Write-Host "`n--- OpenACP install (npm global) ---" -ForegroundColor Cyan

$openacp = Get-Command openacp -ErrorAction SilentlyContinue
if ($openacp) { Write-Ok "openacp on PATH ($($openacp.Source))" }
else { Write-Fail "openacp not on PATH — dashboard OpenACP page -> Install OpenACP (or npm install -g @openacp/cli@$PinnedCliVersion @openacp/discord-adapter@$PinnedAdapterVersion)" }

if ($npm) {
    $globalJson = (npm ls -g --depth=0 --json) 2>$null | ConvertFrom-Json
    $cliVersion = $globalJson.dependencies.'@openacp/cli'.version
    $adapterVersion = $globalJson.dependencies.'@openacp/discord-adapter'.version

    if ($cliVersion -eq $PinnedCliVersion) { Write-Ok "@openacp/cli@$cliVersion matches pinned version" }
    elseif ($cliVersion) { Write-Fail "@openacp/cli@$cliVersion installed but pinned version is $PinnedCliVersion — dashboard OpenACP page -> Install OpenACP to re-pin it" }
    else { Write-Fail "@openacp/cli not found in npm global list" }

    # The global adapter is NOT the copy OpenACP loads — it boots the workspace
    # plugin checked further down. A green line here proves nothing about Discord.
    if ($adapterVersion -eq $PinnedAdapterVersion) { Write-Ok "@openacp/discord-adapter@$adapterVersion matches pinned version (global copy — not the one OpenACP loads)" }
    elseif ($adapterVersion) { Write-Fail "@openacp/discord-adapter@$adapterVersion installed but pinned version is $PinnedAdapterVersion — dashboard OpenACP page -> Install OpenACP to re-pin it" }
    else { Write-Fail "@openacp/discord-adapter not found in npm global list" }
}

# --- OpenACP CLI patch ---------------------------------------------------------
# Without it @openacp/cli cannot load any npm plugin on Windows, so the Discord
# adapter is skipped at boot no matter how correctly everything below is set up.
Write-Host "`n--- OpenACP CLI patch (Windows ESM loader) ---" -ForegroundColor Cyan

$cliPatchScript = Join-Path $root "scripts\patch-openacp-cli.mjs"
if (-not $node) {
    Write-Warn "node not on PATH — cannot check the CLI patch"
} elseif (-not (Test-Path $cliPatchScript)) {
    Write-Fail "patch-openacp-cli.mjs not found at $cliPatchScript"
} else {
    node $cliPatchScript --check *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok "CLI ESM loader is patched" }
    else { Write-Fail "CLI ESM loader is NOT patched — npm plugins cannot load on Windows, so Discord stays silent. Run: node `"$cliPatchScript`" (scripts\start-openacp.ps1 also does this automatically)" }
}

# --- OpenACP workspace --------------------------------------------------------
Write-Host "`n--- OpenACP workspace ---" -ForegroundColor Cyan

$workspace = Join-Path $HOME "openacp-workspace"
$dotOpenacp = Join-Path $workspace ".openacp"
$settingsPath = Join-Path $dotOpenacp "plugins\data\@openacp\discord-adapter\settings.json"

if (Test-Path $workspace) { Write-Ok "workspace folder exists: $workspace" }
else {
    Write-Fail "workspace folder missing: $workspace — create it (New-Item -ItemType Directory `"$workspace`") then run scripts\start-openacp.ps1 once so OpenACP can initialize .openacp\"
}

if (Test-Path $dotOpenacp) { Write-Ok "$dotOpenacp exists — OpenACP has run at least once here" }
else { Write-Fail "$dotOpenacp missing — OpenACP has never been started on this PC. Run scripts\start-openacp.ps1 once before applying a settings bundle" }

if (Test-Path $settingsPath) { Write-Ok "discord-adapter settings.json exists: $settingsPath" }
else { Write-Fail "discord-adapter settings.json missing: $settingsPath — this is exactly what makes /api/openacp/channel-bindings return 503. Configure the bot token manually or use the dashboard's 'Apply bundle to this PC' (needs .openacp\ to exist first, see above)" }

$bundlePath = Join-Path $root "openacp-config\settings.json"
if (Test-Path $bundlePath) { Write-Ok "openacp-config\settings.json bundle present in repo (gitignored)" }
else { Write-Warn "openacp-config\settings.json bundle not present — nothing to import via 'Apply bundle to this PC'; configure the bot token manually or copy the bundle from the source PC" }

# --- Bound workspace folders ---------------------------------------------------
$settingsForBindings = if (Test-Path $settingsPath) { $settingsPath } elseif (Test-Path $bundlePath) { $bundlePath } else { $null }
if ($settingsForBindings) {
    Write-Host "`n--- Bound workspace folders (from $settingsForBindings) ---" -ForegroundColor Cyan
    try {
        $settingsJson = Get-Content $settingsForBindings -Raw | ConvertFrom-Json
        $bindings = $settingsJson.channelBindings
        if ($bindings) {
            $bindings.PSObject.Properties | ForEach-Object {
                $folder = $_.Value.workspace
                if ($folder -and (Test-Path $folder)) { Write-Ok "$folder exists" }
                elseif ($folder) { Write-Fail "$folder does not exist on this PC — OpenACP will drop this channel binding" }
            }
        } else {
            Write-Warn "no channelBindings in $settingsForBindings"
        }
    } catch {
        Write-Warn "could not parse $settingsForBindings as JSON: $_"
    }
}

# --- Discord adapter as a workspace plugin --------------------------------------
# The one check that actually predicts whether Discord works: OpenACP boots only
# what .openacp\plugins.json lists, loaded from .openacp\plugins\node_modules.
# A global npm install satisfies neither, and the hook check below passes anyway
# because it patches the global copy — which is how a completely dead Discord can
# still produce an all-green report.
Write-Host "`n--- Discord adapter (workspace plugin) ---" -ForegroundColor Cyan

$pluginScript = Join-Path $root "scripts\install-openacp-plugin.mjs"
if (-not $node) {
    Write-Warn "node not on PATH — cannot check the workspace plugin"
} elseif (-not (Test-Path $pluginScript)) {
    Write-Fail "install-openacp-plugin.mjs not found at $pluginScript"
} else {
    node $pluginScript --check *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok "adapter installed and registered as a workspace plugin" }
    else { Write-Fail "adapter is NOT a workspace plugin — OpenACP will never load it and Discord stays silent. Run: node `"$pluginScript`" (scripts\start-openacp.ps1 also does this automatically)" }
}

# --- Adapter hook --------------------------------------------------------------
Write-Host "`n--- Channel-bindings hook ---" -ForegroundColor Cyan

$hookScript = Join-Path $root "openacp-channel-bindings\scripts\install-hook.mjs"
if (-not $node) {
    Write-Warn "node not on PATH — cannot check hook"
} elseif (-not (Test-Path $hookScript)) {
    Write-Fail "install-hook.mjs not found at $hookScript"
} elseif (-not (Test-Path (Join-Path $root "openacp-channel-bindings\dist\index.js"))) {
    Write-Warn "channel-bindings module not built — checked above"
} else {
    node $hookScript --check *> $null
    if ($LASTEXITCODE -eq 0) { Write-Ok "adapter hook is installed" }
    else { Write-Fail "adapter hook is NOT installed — dashboard OpenACP page -> Redeploy hook (or node `"$hookScript`")" }
}

# --- Summary ---------------------------------------------------------------
Write-Host ""
if ($script:FailCount -eq 0) {
    Write-Host "=== All checks passed ===" -ForegroundColor Green
} else {
    Write-Host "=== $($script:FailCount) check(s) failed — fix them top to bottom, each later step can depend on the ones above it ===" -ForegroundColor Red
}

# Double-clicking this script in Explorer opens a console that closes itself
# the instant the script ends, taking every red [fail] line with it. Pause so
# it stays readable either way.
if ($Host.Name -eq "ConsoleHost") {
    Write-Host ""
    Read-Host "Press Enter to close"
}
