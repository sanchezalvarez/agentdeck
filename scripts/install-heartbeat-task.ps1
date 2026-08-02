# Creates (or replaces) the "AgentDeck Heartbeat" scheduled task, which is
# what makes this PC show up as an online worker in the dashboard. Nothing
# else in this repo creates it — a fresh PC has no heartbeat at all until
# this has been run once. Safe to re-run.
#
# Runs scripts\heartbeat-silent.vbs (which launches heartbeat.ps1 hidden)
# every 15 minutes. See AGENTS.md "Worker heartbeat task" for the
# "run whether the user is logged on or not" alternative, which needs
# administrator rights.
$ErrorActionPreference = "Stop"

$taskName = "AgentDeck Heartbeat"
$vbsPath = Join-Path $PSScriptRoot "heartbeat-silent.vbs"

if (-not (Test-Path $vbsPath)) {
    Write-Error "heartbeat-silent.vbs not found next to this script: $vbsPath"
}

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Write-Host "Task '$taskName' already exists — removing it first so it points at this checkout." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Description "Posts a worker heartbeat to Agent Deck every 15 minutes (scripts\heartbeat.ps1 via heartbeat-silent.vbs)." `
    | Out-Null

Write-Host "Created scheduled task '$taskName' -> $vbsPath (every 15 minutes)." -ForegroundColor Green
Write-Host "Running it once now to confirm it actually reaches the backend..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3
$info = Get-ScheduledTaskInfo -TaskName $taskName
if ($info.LastTaskResult -eq 0) {
    Write-Host "OK — worker heartbeat sent. Check the Workers page in the dashboard." -ForegroundColor Green
} else {
    Write-Host "Task ran but reported exit code $($info.LastTaskResult) — check .\scripts\heartbeat.ps1 output by running it directly:" -ForegroundColor Yellow
    Write-Host "  .\scripts\heartbeat.ps1"
}
