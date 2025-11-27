# Remote Office Sync - PowerShell script
# Run with: powershell -ExecutionPolicy Bypass -File run_sync.ps1

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
    Write-Host "WARNING: config.yaml not found!" -ForegroundColor Yellow
    Write-Host "Creating config.yaml from config.example.yaml..."
    Copy-Item "config.example.yaml" "config.yaml"
    Write-Host ""
    Write-Host "IMPORTANT: Edit config.yaml and set your paths:" -ForegroundColor Yellow
    Write-Host "  left_root: C:\your\local\path" -ForegroundColor Cyan
    Write-Host "  right_root: P:\your\network\path" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press Enter after editing config.yaml"
}

# Run sync
Write-Host ""
Write-Host "Starting Remote Office Sync..." -ForegroundColor Green
Write-Host ""
python -m remote_office_sync.main --config config.yaml

# Show log
if (Test-Path "sync.log") {
    Write-Host ""
    Write-Host "[OK] Sync complete! Check sync.log for details." -ForegroundColor Green
}

Read-Host "Press Enter to exit"
