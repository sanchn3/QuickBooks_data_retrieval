@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  build.bat — Build QB_Weekly_Sync.exe with PyInstaller
REM
REM  Requirements (dev machine only):
REM    - 32-bit Python 3.11 installed at C:\Python311_32\
REM    - All dependencies installed:
REM        C:\Python311_32\python.exe -m pip install -r requirements.txt
REM
REM  Output: dist\QB_Weekly_Sync.exe
REM  Deploy: copy dist\QB_Weekly_Sync.exe and .env to target machine
REM ──────────────────────────────────────────────────────────────────────────

setlocal

set PYTHON=C:\Python311_32\python.exe

REM Verify 32-bit Python is available
if not exist "%PYTHON%" (
    echo [ERROR] 32-bit Python 3.11 not found at %PYTHON%
    echo         Install from https://www.python.org/downloads/windows/
    echo         Choose "Windows installer (32-bit)" for Python 3.11.x
    pause
    exit /b 1
)

REM Install build dependencies (pyinstaller) if not already present
echo Checking build dependencies...
"%PYTHON%" -c "import PyInstaller" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing build dependencies from requirements-build.txt...
    "%PYTHON%" -m pip install -r "%~dp0requirements-build.txt"
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install build dependencies.
        pause
        exit /b 1
    )
)

REM Build the exe
echo.
echo Building QB_Weekly_Sync.exe ...
echo.
"%PYTHON%" -m PyInstaller QB_Weekly_Sync.spec --clean

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller build failed. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD SUCCESSFUL
echo  Output: %~dp0dist\QB_Weekly_Sync.exe
echo ============================================================
echo.
echo  Next steps — deploy to target machine:
echo.
echo    1. Copy  dist\QB_Weekly_Sync.exe  to target (e.g. C:\QB_Weekly_Sync\)
echo    2. Copy  .env.example             to same folder, rename to .env
echo    3. Fill in SUPABASE_URL, SUPABASE_KEY, QB_COMPANY_FILE in .env
echo    4. Run setup_scheduler.bat as Administrator on target machine
echo.

endlocal
pause
