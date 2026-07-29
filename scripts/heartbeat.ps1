# Sends a worker heartbeat to the local Agent Hub.
# Runs from the "AgentHub Heartbeat" scheduled task (see README). Posts directly
# to the HTTP API — no Python interpreter startup on every run. Reads the write
# token from the repository .env so it does not depend on the task's environment.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib.ps1")

$token = Get-EnvValue "AGENT_HUB_WRITE_TOKEN" ""
$hubUrl = Get-EnvValue "AGENT_HUB_URL" "http://127.0.0.1:8765"

$payload = @{
    worker              = "Rembrosoft-Main-PC"
    hostname            = $env:COMPUTERNAME
    operating_system    = "Windows 11"
    claude_available    = [bool](Get-Command claude -ErrorAction SilentlyContinue)
    codex_available     = [bool](Get-Command codex -ErrorAction SilentlyContinue)
    unity_available     = (Test-Path "C:\Program Files\Unity\Hub\Editor") -or (Test-Path "C:\Program Files\Unity Hub\Unity Hub.exe")
    unity_mcp_available = [bool](Test-Path "C:\unity\TheLosers\.mcp.json")
} | ConvertTo-Json

$headers = @{}
if ($token) { $headers["Authorization"] = "Bearer $token" }

# Exit codes match agent-report: 0 success, 1 API error, 3 connection error.
try {
    $result = Invoke-RestMethod -Method Post -Uri "$hubUrl/api/workers/heartbeat" `
        -Headers $headers -ContentType "application/json" -Body $payload -TimeoutSec 15
    Write-Host "Heartbeat recorded for worker '$($result.name)' (status: $($result.status), last seen: $($result.last_seen_at))"
    exit 0
} catch {
    Write-Host "Heartbeat failed: $($_.Exception.Message)"
    if ($_.Exception.Response) { exit 1 } else { exit 3 }
}
