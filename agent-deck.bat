@echo off
REM The one file to double-click. Everything else lives in scripts\.
REM
REM   Double-click              -> menu
REM   agent-deck.bat start      -> backend + dashboard + OpenACP
REM   agent-deck.bat stop       -> shut everything down
REM   agent-deck.bat install    -> prerequisites + setup (first run on a new PC)
REM
REM Extra arguments are passed through, e.g.  agent-deck.bat start -NoBrowser
setlocal
cd /d "%~dp0"

REM First argument is the action; everything after it goes to PowerShell.
set "ACTION=%~1"
set "REST="
:collect
shift
if "%~1"=="" goto collected
set "REST=%REST% %1"
goto collect
:collected

set "FROMMENU="
set "TRIES=0"
if not "%ACTION%"=="" goto dispatch

:menu
REM Bounded: on a closed stdin "set /p" leaves CHOICE empty every time, and an
REM unbounded retry would spin forever instead of exiting.
set /a TRIES+=1
if %TRIES% GTR 3 (
    echo No valid choice - exiting.
    exit /b 1
)
set "FROMMENU=1"
echo.
echo    Agent Deck
echo    ----------
echo.
echo     [1]  Start    backend, dashboard and OpenACP
echo     [2]  Stop     shut everything down
echo     [3]  Install  prerequisites + setup, for a new PC
echo     [Q]  Quit
echo.
set "CHOICE="
set /p "CHOICE=Choose: "
if /i "%CHOICE%"=="1" set "ACTION=start"
if /i "%CHOICE%"=="2" set "ACTION=stop"
if /i "%CHOICE%"=="3" set "ACTION=install"
if /i "%CHOICE%"=="q" exit /b 0
if "%ACTION%"=="" goto menu

:dispatch
set "SCRIPT="
if /i "%ACTION%"=="start"   set "SCRIPT=start-all.ps1"
if /i "%ACTION%"=="stop"    set "SCRIPT=stop-all.ps1"
if /i "%ACTION%"=="install" set "SCRIPT=bootstrap.ps1"
if /i "%ACTION%"=="setup"   set "SCRIPT=bootstrap.ps1"
if not defined SCRIPT (
    echo Unknown action "%ACTION%" - expected start, stop or install.
    exit /b 1
)

REM PowerShell 7 if present; Windows PowerShell 5.1 otherwise, which is all a
REM fresh PC has before bootstrap installs pwsh.
set "PS=powershell"
where pwsh >nul 2>&1
if %errorlevel%==0 set "PS=pwsh"

%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\%SCRIPT%"%REST%
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
    echo.
    echo %ACTION% failed with exit code %CODE%.
    pause
    exit /b %CODE%
)

REM Started from a double-click: keep the window up so the output is readable.
if defined FROMMENU (
    echo.
    pause
)
endlocal
