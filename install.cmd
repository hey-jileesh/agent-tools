@echo off
REM Install (sync) agent-tools skills into a target project (Windows).
REM
REM Skill directory by agent:
REM   Windsurf / GitHub Copilot -> .agent\skills      (default)
REM   Claude Code / Cowork       -> .claude\skills
REM   Devin                      -> .cognition\skills
REM
REM Usage:
REM   install.cmd [--agent NAME] [--target DIR] [--skills "a b c"] [--all] [--list] [-y]
REM     --agent  NAME  agent|windsurf|copilot (default), claude|cowork, devin|cognition
REM     --target DIR   project root to install into (default: current directory)
REM     --skills LIST  space-separated skill names in quotes (default: all)
REM     --list         list available skills and exit
REM     -y             non-interactive; accept defaults
REM
REM Re-running syncs: existing skills are mirrored (robocopy /MIR), so install == update.
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

set "AGENT="
set "TARGET=."
set "SKILLS="
set "ASSUME_YES=0"
set "DO_LIST=0"

:parse
if "%~1"=="" goto afterparse
if /i "%~1"=="--agent"  ( set "AGENT=%~2" & shift & shift & goto parse )
if /i "%~1"=="--target" ( set "TARGET=%~2" & shift & shift & goto parse )
if /i "%~1"=="--skills" ( set "SKILLS=%~2" & shift & shift & goto parse )
if /i "%~1"=="--all"    ( set "SKILLS=" & shift & goto parse )
if /i "%~1"=="--list"   ( set "DO_LIST=1" & shift & goto parse )
if /i "%~1"=="-y"       ( set "ASSUME_YES=1" & shift & goto parse )
if /i "%~1"=="--yes"    ( set "ASSUME_YES=1" & shift & goto parse )
if /i "%~1"=="-h"       ( goto help )
if /i "%~1"=="--help"   ( goto help )
echo Unknown argument: %~1
goto help

:afterparse
REM Discover skills: subdirectories containing SKILL.md
set "ALL_SKILLS="
for /d %%D in ("%SCRIPT_DIR%\*") do (
  if exist "%%D\SKILL.md" set "ALL_SKILLS=!ALL_SKILLS! %%~nxD"
)

if "%DO_LIST%"=="1" (
  for %%S in (%ALL_SKILLS%) do echo %%S
  goto end
)

REM Interactive selection if no agent/skills given and not -y
if "%AGENT%"=="" if "%SKILLS%"=="" if "%ASSUME_YES%"=="0" (
  echo Select coding agent ^(skills directory^):
  echo   1^) .agent\skills      Windsurf, GitHub Copilot   [default]
  echo   2^) .claude\skills     Claude Code, Cowork
  echo   3^) .cognition\skills  Devin
  set /p "CH=Choice [1]: "
  if "!CH!"=="2" set "AGENT=claude"
  if "!CH!"=="3" set "AGENT=devin"
  echo Available skills:%ALL_SKILLS%
  set /p "SKILLS=Install which? (space-separated, blank = all): "
)

if "%AGENT%"=="" set "AGENT=agent"

REM Map agent -> skills directory
set "SKDIR="
if /i "%AGENT%"=="agent"     set "SKDIR=.agent\skills"
if /i "%AGENT%"=="windsurf"  set "SKDIR=.agent\skills"
if /i "%AGENT%"=="copilot"   set "SKDIR=.agent\skills"
if /i "%AGENT%"=="claude"    set "SKDIR=.claude\skills"
if /i "%AGENT%"=="cowork"    set "SKDIR=.claude\skills"
if /i "%AGENT%"=="devin"     set "SKDIR=.cognition\skills"
if /i "%AGENT%"=="cognition" set "SKDIR=.cognition\skills"
if "%SKDIR%"=="" (
  echo Unknown agent '%AGENT%'. Use agent^|claude^|devin ^(see --help^).
  exit /b 2
)

if "%SKILLS%"=="" set "SKILLS=%ALL_SKILLS%"

REM Resolve target to an absolute path
pushd "%TARGET%" 2>nul || ( echo Target directory not found: %TARGET% & exit /b 2 )
set "TARGET_ABS=%CD%"
popd
if /i "%TARGET_ABS%"=="%SCRIPT_DIR%" (
  echo Refusing to install into the agent-tools repo itself. Pass --target ^<project^>.
  exit /b 2
)

set "DEST=%TARGET_ABS%\%SKDIR%"
if not exist "%DEST%" mkdir "%DEST%"
echo Installing into: %DEST%

set /a COUNT=0
for %%S in (%SKILLS%) do (
  if exist "%SCRIPT_DIR%\%%S\SKILL.md" (
    set "ACTION=installed"
    if exist "%DEST%\%%S" set "ACTION=synced"
    robocopy "%SCRIPT_DIR%\%%S" "%DEST%\%%S" /MIR /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
    if errorlevel 8 (
      echo   ERROR copying %%S
    ) else (
      echo   !ACTION!: %%S
      set /a COUNT+=1
    )
  ) else (
    echo   skip:   '%%S' is not a skill ^(no SKILL.md^)
  )
)

echo Done - !COUNT! skill(s) in %SKDIR% for agent '%AGENT%'.
goto end

:help
REM Print the header comment block as help
for /f "tokens=1,* delims=:" %%a in ('findstr /n "^REM" "%~f0"') do (
  set "line=%%b"
  setlocal enabledelayedexpansion
  echo(!line:~4!
  endlocal
)
goto end

:end
endlocal
