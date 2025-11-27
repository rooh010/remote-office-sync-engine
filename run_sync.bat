@echo off
REM Remote Office Sync - Windows batch script

REM Check if venv exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment
        echo Make sure Python 3.11+ is installed and in PATH
        pause
        exit /b 1
    )
)

REM Check if pCloud is running
echo Checking pCloud status...
tasklist /FI "IMAGENAME eq pCloud.exe" 2>NUL | find /I /N "pCloud.exe">NUL
if errorlevel 1 (
    echo [ERROR] pCloud is not running!
    echo Please start pCloud.exe before running this sync script.
    echo The P:\ drive must be available for sync to work.
    echo.
    pause
    exit /b 1
)
echo [OK] pCloud is running

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -q -r requirements.txt

REM Check if config.yaml exists
if not exist config.yaml (
    echo.
    echo [ERROR] config.yaml not found!
    echo.
    echo To create your config file:
    echo   1. Copy the template: copy config.template.yaml config.yaml
    echo   2. Edit config.yaml and set your paths
    echo   3. Use FORWARD SLASHES: "C:/your/path/" not "C:\your\path\"
    echo.
    echo See README.md for complete setup instructions.
    echo.
    pause
    exit /b 1
)

REM Run sync
echo.
echo Starting Remote Office Sync...
echo.

REM Check for --no-dry-run parameter
if "%1"=="--no-dry-run" (
    echo Running with ACTUAL FILE SYNCHRONIZATION ^(dry run disabled^)
    echo.
    python -m remote_office_sync.main --config config.yaml --no-dry-run
) else (
    echo Running in DRY RUN mode ^(no changes will be made^)
    echo To perform actual sync, run: run_sync.bat --no-dry-run
    echo.
    python -m remote_office_sync.main --config config.yaml
)

REM Show log file location
if exist sync.log (
    echo.
    echo Sync complete! Check sync.log for details.
)

pause
