# Helpers shared by the Agent Deck scripts. Dot-source it at the top of a script:
#
#     . (Join-Path $PSScriptRoot "lib.ps1")
#
# Only put things here that more than one script needs — single-purpose logic
# belongs in the script that owns it.

function Test-Listening {
    # True when something accepts TCP connections on a local port. Used to spot
    # a service that is already up, including a foreground OpenACP instance,
    # which writes no pid file and so reads as "offline" to "openacp status".
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-EnvValue {
    # One key from the repository .env, or $Default when it is missing.
    param([string]$Name, [string]$Default)
    # $PSScriptRoot is this file's directory even when another script dot-sources
    # it, so the lookup depends on neither the caller nor the current location.
    $envFile = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match "^\s*$Name\s*=\s*(.+)$") { return $Matches[1].Trim() }
        }
    }
    return $Default
}

function Stop-OpenAcpNodeProcess {
    # Kills OpenACP's own node processes. Needed because "openacp stop" only
    # finds a daemonized instance: a foreground one writes no pid file and
    # survives, and a crashed daemon can leave its node process behind.
    param([string]$Label = "leftover OpenACP process")
    Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object { $_.CommandLine -like "*@openacp*" } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                Write-Host "[stop]  $Label (pid $($_.ProcessId))" -ForegroundColor Green
            } catch { }
        }
}
