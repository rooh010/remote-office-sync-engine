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

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies if needed
pip install -q -r requirements.txt

REM Check if config.yaml exists
if not exist config.yaml (
    echo.
    echo WARNING: config.yaml not found!
    echo Creating config.yaml from config.example.yaml...
    copy config.example.yaml config.yaml
    echo.
    echo IMPORTANT: Edit config.yaml and set your paths:
    echo   left_root: C:\your\local\path
    echo   right_root: P:\your\network\path
    echo.
    pause
)

REM Run sync
echo.
echo Starting Remote Office Sync...
echo.
python -m remote_office_sync.main --config config.yaml

REM Show log file location
if exist sync.log (
    echo.
    echo Sync complete! Check sync.log for details.
)

pause
