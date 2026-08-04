# Kill leaked cloudflared tunnel processes spawned by the OpenACP CLI.
#
# OpenACP starts its tunnel as a child cloudflared.exe from ~\.openacp\bin.
# When the CLI is killed or restarted, that child is orphaned and keeps
# running — repeated restarts pile up tunnels (each ~30 MB RAM + network
# traffic). By default only orphans (parent process gone) are killed, so a
# tunnel whose OpenACP parent is alive is left alone. -All kills every
# OpenACP-owned tunnel, for use when stopping OpenACP itself.
param(
    [switch]$All
)

$ErrorActionPreference = "Stop"

$tunnels = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" |
    Where-Object { $_.CommandLine -like "*\.openacp\*" }

$killed = 0
foreach ($tunnel in $tunnels) {
    if (-not $All) {
        $parentAlive = [bool](Get-Process -Id $tunnel.ParentProcessId -ErrorAction SilentlyContinue)
        if ($parentAlive) { continue }
    }
    try {
        Stop-Process -Id $tunnel.ProcessId -Force -ErrorAction Stop
        $label = if ($All) { "cloudflared tunnel" } else { "orphaned cloudflared tunnel" }
        Write-Host "[stop]  $label (pid $($tunnel.ProcessId))" -ForegroundColor Green
        $killed++
    } catch { }
}

if ($killed -eq 0) {
    Write-Host "[skip]  no leaked cloudflared tunnels" -ForegroundColor Yellow
}
