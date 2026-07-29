@echo off
REM Double-click on a fresh PC: installs Python 3.12+, Node 20+ and PowerShell 7
REM (via winget) if missing, then runs setup (venv + node_modules + .env).
REM
REM This is the one step that cannot be a dashboard button, because the
REM dashboard itself needs Python and Node to run.
setlocal
cd /d "%~dp0"

where pwsh >nul 2>&1
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" %*
)

if errorlevel 1 (
    echo.
    echo Bootstrap failed with exit code %errorlevel%.
)

echo.
pause
endlocal
