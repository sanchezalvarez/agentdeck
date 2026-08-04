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

# --- OpenACP CLI ESM loader patch ------------------------------------------
# Without this, @openacp/cli cannot load ANY npm plugin on Windows, the Discord
# adapter among them, and Discord goes completely silent while still looking
# installed everywhere you would check. Verified before the hook below because an
# adapter that never loads makes the hook irrelevant. Restored to its broken
# state by every "openacp update", so it is checked on every start.
$cliPatchScript = Join-Path $PSScriptRoot "patch-openacp-cli.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[skip]  node not on PATH - OpenACP CLI patch not verified" -ForegroundColor Yellow
} elseif (-not (Test-Path $cliPatchScript)) {
    Write-Host "[skip]  patch-openacp-cli.mjs not found - OpenACP CLI patch not verified" -ForegroundColor Yellow
} else {
    node $cliPatchScript --check 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[ok]    OpenACP CLI ESM loader patched" -ForegroundColor DarkGray
    } else {
        Write-Host "[fix]   OpenACP CLI unpatched - npm plugins cannot load on Windows, patching" -ForegroundColor Cyan
        node $cliPatchScript 2>&1 | ForEach-Object { Write-Host "        $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn]  CLI patch failed - the Discord adapter will NOT load" -ForegroundColor Red
        }
    }
    # A non-zero code from the check above is an answer, not this script's result.
    $global:LASTEXITCODE = 0
}

# --- Discord adapter as a workspace plugin ---------------------------------
# OpenACP boots adapters from .openacp\plugins + plugins.json, not from the global
# npm install the dashboard's "Install OpenACP" performs. Neither `openacp install`
# nor the onboarding wizard can put it there on Windows, so a fresh PC would run
# with no Discord adapter at all — silently. Comes after the CLI patch (an
# unpatched CLI cannot load the plugin anyway) and before the hook, which has
# nothing to patch until the adapter exists.
$pluginScript = Join-Path $PSScriptRoot "install-openacp-plugin.mjs"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[skip]  node not on PATH - Discord workspace plugin not verified" -ForegroundColor Yellow
} elseif (-not (Test-Path $pluginScript)) {
    Write-Host "[skip]  install-openacp-plugin.mjs not found - workspace plugin not verified" -ForegroundColor Yellow
} else {
    node $pluginScript --check 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[ok]    Discord adapter installed as a workspace plugin" -ForegroundColor DarkGray
    } else {
        Write-Host "[fix]   Discord adapter not a workspace plugin - installing it" -ForegroundColor Cyan
        node $pluginScript 2>&1 | ForEach-Object { Write-Host "        $_" }
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn]  workspace plugin install failed - Discord will NOT work" -ForegroundColor Red
        }
    }
    # A non-zero code from the check above is an answer, not this script's result.
    $global:LASTEXITCODE = 0
}

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

# --- Reconnect network workspaces ------------------------------------------
# Windows restores a persistent drive mapping lazily: after a reboot Z:\ is a
# known mapping but resolves as missing until something first touches it. The
# adapter stats every bound workspace when a Discord message arrives, so an
# untouched drive makes that binding read as broken. Touch the drives here,
# while nobody is waiting for an answer in Discord.
$settingsFile = Join-Path $workspace ".openacp\plugins\data\@openacp\discord-adapter\settings.json"

if (-not (Test-Path $settingsFile)) {
    Write-Host "[skip]  no Discord adapter settings yet - no workspaces to reconnect" -ForegroundColor DarkGray
} else {
    $roots = @()
    try {
        # settings.json also holds the Discord bot token: read it for the
        # workspace paths only, and never put file content into a message.
        $bindings = (Get-Content $settingsFile -Raw | ConvertFrom-Json).channelBindings
        if ($bindings) {
            $roots = @(
                $bindings.PSObject.Properties.Value |
                    ForEach-Object { $_.workspace } |
                    Where-Object { $_ } |
                    ForEach-Object { [System.IO.Path]::GetPathRoot($_) } |
                    Where-Object { $_ } |
                    Select-Object -Unique
            )
        }
    } catch {
        Write-Host "[warn]  channel bindings unreadable - network workspaces not reconnected" -ForegroundColor Yellow
    }

    # Win32_NetworkConnection lists persistent mappings even while they are
    # disconnected, which is exactly the state this step exists to fix.
    $mapped = @()
    try {
        $mapped = @(Get-CimInstance Win32_NetworkConnection -ErrorAction Stop |
            ForEach-Object { $_.LocalName } | Where-Object { $_ })
    } catch { }

    $remote = @($roots | Where-Object { $_.StartsWith("\\") -or ($mapped -contains $_.TrimEnd("\")) })

    if ($remote.Count -eq 0) {
        Write-Host "[ok]    no network workspaces in channel bindings" -ForegroundColor DarkGray
    } else {
        # Test-Path against an unreachable share blocks for the SMB redirector's
        # timeout, so the probe runs where start-up can walk away from it. The
        # job shares this logon session, so the reconnect it triggers is the one
        # OpenACP will see.
        $probe = Start-Job -ScriptBlock {
            param($paths)
            foreach ($p in $paths) { [pscustomobject]@{ Path = $p; Ok = (Test-Path -LiteralPath $p) } }
        } -ArgumentList (, $remote)

        if (Wait-Job $probe -Timeout 25) {
            foreach ($result in (Receive-Job $probe)) {
                if ($result.Ok) {
                    Write-Host "[ok]    network workspace reachable: $($result.Path)" -ForegroundColor DarkGray
                } else {
                    Write-Host "[warn]  network workspace unreachable: $($result.Path)" -ForegroundColor Yellow
                    Write-Host "        bindings under it are ignored until it comes back (retried every 30s)"
                }
            }
        } else {
            Write-Host "[warn]  network workspaces did not answer in 25s - starting anyway" -ForegroundColor Yellow
            Stop-Job $probe
        }
        Remove-Job $probe -Force
    }
}

Set-Location $workspace
# "--foreground" is the only way to keep the server in this window: plain
# "openacp start" always daemonizes, whatever runMode says in the config.
openacp --foreground
