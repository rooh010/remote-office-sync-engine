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
    echo WARNING: config.yaml not found!
    echo Creating config.yaml...
    (
        echo # Remote Office Sync Configuration
        echo # Edit paths below with your actual folders
        echo.
        echo left_root: "C:/Users/Andy/Documents"
        echo right_root: "C:/Users/Andy/OneDrive"
        echo.
        echo soft_delete:
        echo   enabled: true
        echo   max_size_mb: 20
        echo.
        echo conflict_policy:
        echo   modify_modify: clash
        echo   new_new: clash
        echo   metadata_conflict: clash
        echo.
        echo ignore:
        echo   extensions:
        echo     - .tmp
        echo     - .bak
        echo     - .log
        echo   filenames_prefix:
        echo     - .
        echo     - "~"
        echo   filenames_exact:
        echo     - thumbs.db
        echo     - desktop.ini
        echo     - System Volume Information
        echo.
        echo email:
        echo   enabled: false
        echo.
        echo logging:
        echo   level: INFO
        echo   file_path: "C:/logs/sync.log"
    ) > config.yaml
    echo.
    echo ✓ Created config.yaml
    echo.
    echo IMPORTANT: Edit config.yaml and set your actual paths!
    echo.
    echo Opening config.yaml for editing...
    timeout /t 2 /nobreak
    notepad config.yaml
    echo.
    echo After editing, run this script again.
    pause
    exit /b 0
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
