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

REM Check if pCloud is running (unless --no-pcloud flag is passed)
REM Use echo to check all arguments without consuming them
echo %* | findstr /C:"--no-pcloud" >nul
if errorlevel 1 (
    REM --no-pcloud not found, do the check
    echo Checking pCloud status...
    tasklist /FI "IMAGENAME eq pCloud.exe" 2>NUL | find /I /N "pCloud.exe">NUL
    if errorlevel 1 (
        echo [ERROR] pCloud is not running!
        echo Please start pCloud.exe before running this sync script.
        echo The P:\ drive must be available for sync to work.
        echo.
        echo To skip this check, use: run_sync.bat --no-pcloud
        echo.
        pause
        exit /b 1
    )
    echo [OK] pCloud is running
)

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

REM Build argument list for Python, filtering out --no-pcloud
set PYTHON_ARGS=
:build_args
if "%1"=="" goto run_python
if not "%1"=="--no-pcloud" (
    set PYTHON_ARGS=%PYTHON_ARGS% %1
)
shift
goto build_args

:run_python
REM Check if --no-dry-run is in the arguments
echo %PYTHON_ARGS% | findstr /C:"--no-dry-run" >nul
if errorlevel 1 (
    echo Running in DRY RUN mode ^(no changes will be made^)
    echo To perform actual sync, run: run_sync.bat --no-dry-run
    echo.
) else (
    echo Running with ACTUAL FILE SYNCHRONIZATION ^(dry run disabled^)
    echo.
)

python -m remote_office_sync.main --config config.yaml%PYTHON_ARGS%

REM Show log file location
if exist sync.log (
    echo.
    echo Sync complete! Check sync.log for details.
)

pause
