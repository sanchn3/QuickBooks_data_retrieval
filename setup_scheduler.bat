@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  setup_scheduler.bat
REM  Registers the QB_Weekly_Sync task in Windows Task Scheduler.
REM
REM  Requirements:
REM    - Run as Administrator
REM    - QB_Weekly_Sync.exe and .env must be in the same folder as this script
REM      (default deploy path: C:\QB_Weekly_Sync\)
REM ──────────────────────────────────────────────────────────────────────────

setlocal

set TASK_NAME=QB_Weekly_Sync
set DEPLOY_DIR=%~dp0

echo.
echo Registering Windows Task Scheduler job: %TASK_NAME%
echo Deploy folder : %DEPLOY_DIR%
echo Executable    : %DEPLOY_DIR%QB_Weekly_Sync.exe
echo Schedule      : Every Monday at 02:00 AM
echo.

REM Verify the exe exists
if not exist "%DEPLOY_DIR%QB_Weekly_Sync.exe" (
    echo [ERROR] QB_Weekly_Sync.exe not found in %DEPLOY_DIR%
    echo         Copy the exe here before registering the task.
    pause
    exit /b 1
)

REM Delete existing task if present (ignore error)
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Import the XML task definition (handles timezone correctly)
schtasks /create /xml "%DEPLOY_DIR%scheduler_task.xml" /tn "%TASK_NAME%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Task "%TASK_NAME%" registered successfully.
    echo.
    echo To test immediately:
    echo   schtasks /run /tn "%TASK_NAME%"
    echo.
    echo To view task status:
    echo   schtasks /query /tn "%TASK_NAME%" /fo LIST /v
) else (
    echo.
    echo [ERROR] Failed to register task. Make sure you are running as Administrator.
    echo         Alternatively, import scheduler_task.xml manually via Task Scheduler GUI.
)

endlocal
pause
