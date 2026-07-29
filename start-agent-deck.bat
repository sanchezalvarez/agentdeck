@echo off
REM Double-click launcher: starts the Agent Deck backend, the dashboard and the
REM OpenACP daemon. Anything already running is left alone.
REM
REM Pass -NoBrowser to skip opening the dashboard automatically.
setlocal
cd /d "%~dp0"

where pwsh >nul 2>&1
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-all.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-all.ps1" %*
)

if errorlevel 1 (
    echo.
    echo Launcher failed with exit code %errorlevel%.
    pause
)

endlocal
