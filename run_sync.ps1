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

# Check if pCloud is running (unless --no-pcloud flag is passed or disabled in config)
$skipPCloudCheck = $false

# Check command-line flag
if ($args -contains "--no-pcloud") {
    $skipPCloudCheck = $true
}

# Check config.yaml setting (if file exists)
if ((Test-Path "config.yaml") -and -not $skipPCloudCheck) {
    $configContent = Get-Content "config.yaml" -Raw
    # Look for pcloud_check: enabled: false (accounting for comments and whitespace)
    if ($configContent -match '(?m)^\s*pcloud_check\s*:[\s\S]*?enabled\s*:\s*false') {
        $skipPCloudCheck = $true
    }
}

if (-not $skipPCloudCheck) {
    Write-Host "Checking pCloud status..."
    $pCloudRunning = Get-Process -Name "pCloud" -ErrorAction SilentlyContinue
    if (-not $pCloudRunning) {
        Write-Host "[ERROR] pCloud is not running!" -ForegroundColor Red
        Write-Host "Please start pCloud.exe before running this sync script." -ForegroundColor Yellow
        Write-Host "The P:\ drive must be available for sync to work." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To skip this check, use: run_sync.ps1 --no-pcloud" -ForegroundColor Yellow
        Write-Host "Or set pcloud_check.enabled: false in config.yaml" -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "[OK] pCloud is running"
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
# Pass through arguments except --no-pcloud (which is script-level only)
$pythonArgs = $args | Where-Object { $_ -ne "--no-pcloud" }
python -m remote_office_sync.main --config config.yaml $pythonArgs

# Show log
if (Test-Path "sync.log") {
    Write-Host ""
    Write-Host "[OK] Sync complete! Check sync.log for details." -ForegroundColor Green
}

Read-Host "Press Enter to exit"
