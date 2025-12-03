# Remote Office Sync - PowerShell script
# Run with: powershell -ExecutionPolicy Bypass -File run_sync.ps1
# Pass arguments: powershell -ExecutionPolicy Bypass -File run_sync.ps1 --no-dry-run

# Change to script directory to ensure paths work correctly
Set-Location $PSScriptRoot

Write-Host "Remote Office Sync Engine" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green
Write-Host ""

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] Python found: $pythonVersion"
} catch {
    Write-Host "[ERROR] Python not found. Install Python 3.11+ and add to PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create venv if not exists
if (!(Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[OK] Virtual environment created"
}

# Activate venv
Write-Host "Activating virtual environment..."
& ".\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "Installing dependencies..."
pip install -q -r requirements.txt

# Check config file
if (!(Test-Path "config.yaml")) {
    Write-Host ""
    Write-Host "[ERROR] config.yaml not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "To create your config file:" -ForegroundColor Yellow
    Write-Host "  1. Copy the template: copy config.template.yaml config.yaml"
    Write-Host "  2. Edit config.yaml and set your paths"
    Write-Host "  3. Use FORWARD SLASHES: 'C:/your/path/' not 'C:\your\path\'" -ForegroundColor Red
    Write-Host ""
    Write-Host "See README.md for complete setup instructions."
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Run sync
Write-Host ""
Write-Host "Starting Remote Office Sync..." -ForegroundColor Green
Write-Host ""
python -m remote_office_sync.main --config config.yaml $args

# Show log
if (Test-Path "sync.log") {
    Write-Host ""
    Write-Host "[OK] Sync complete! Check sync.log for details." -ForegroundColor Green
}

Read-Host "Press Enter to exit"
