@echo off
REM Double-click stopper: kills the Agent Hub backend, the dashboard and the
REM OpenACP daemon. Closing the console windows alone does not always do this.
REM
REM Pass -KeepOpenAcp to leave the OpenACP daemon running.
setlocal
cd /d "%~dp0"

where pwsh >nul 2>&1
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-all.ps1" %*
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-all.ps1" %*
)

echo.
pause

endlocal
