@echo off
REM Double-click launcher: backend, dashboard and OpenACP. Anything already
REM running is left alone.
REM
REM This is a shortcut for "agent-deck.bat start" and holds no logic of its own —
REM the pwsh/powershell dispatch lives in agent-deck.bat, in one place.
REM
REM Extra arguments are passed through, e.g.  start-agent-deck.bat -NoBrowser
call "%~dp0agent-deck.bat" start %*
set "CODE=%errorlevel%"

REM agent-deck.bat already pauses when the action fails, so pausing again here
REM would ask twice. A clean run still needs it, or a double-clicked window
REM closes before its output can be read.
if "%CODE%"=="0" pause
exit /b %CODE%
