# Create test directory structure in C:\pdrive_local
$root = 'C:\pdrive_local'

Write-Host "Creating test directory structure in $root..." -ForegroundColor Cyan

# Create main folders
@('Documents', 'Projects', 'Media', 'Archive', 'Work', 'Personal') | ForEach-Object {
    New-Item -ItemType Directory -Path "$root\$_" -Force | Out-Null
    Write-Host "  Created: $_"
}

# Create subfolders
$subfolders = @(
    'Documents\Reports',
    'Documents\Contracts',
    'Projects\Website',
    'Projects\Mobile',
    'Media\Photos',
    'Media\Videos',
    'Work\2024',
    'Work\2025'
)

Write-Host ""
Write-Host "Creating subfolders..." -ForegroundColor Cyan
$subfolders | ForEach-Object {
    New-Item -ItemType Directory -Path "$root\$_" -Force | Out-Null
    Write-Host "  Created: $_"
}

# Create test files with various content
Write-Host ""
Write-Host "Creating test files..." -ForegroundColor Cyan

# Text files
'This is a test report from 2024' | Set-Content "$root\Documents\Reports\Q1_Report.txt"
'Annual summary document with important data' | Set-Content "$root\Documents\Reports\Annual_Summary.txt"
'Contract terms and conditions for project XYZ' | Set-Content "$root\Documents\Contracts\Contract_001.txt"
'Website development project scope and timeline' | Set-Content "$root\Projects\Website\README.txt"
'Mobile app feature list and requirements' | Set-Content "$root\Projects\Mobile\spec.txt"

# Configuration files
'[General]
name=TestConfig
version=1.0
enabled=true' | Set-Content "$root\Projects\Website\config.ini"

# Log files
'[2025-01-01] Application started successfully
[2025-01-01] Database connection established
[2025-01-02] Backup completed' | Set-Content "$root\Work\2025\application.log"

# CSV-like files
'Name,Department,Salary
John Doe,Engineering,95000
Jane Smith,Marketing,85000
Bob Johnson,Sales,90000' | Set-Content "$root\Work\2024\employees.csv"

# Create some files in Media folder
'Sample photo metadata' | Set-Content "$root\Media\Photos\vacation_2024.jpg"
'Sample video metadata' | Set-Content "$root\Media\Videos\tutorial.mp4"
'Sample audio metadata' | Set-Content "$root\Media\Audio_file.mp3"

# Archive folder
'Old backup data from 2023' | Set-Content "$root\Archive\backup_2023.txt"
'Deprecated code archive' | Set-Content "$root\Archive\old_version.bak"

# Personal folder
'Personal notes and reminders' | Set-Content "$root\Personal\notes.txt"
'My secret todo list' | Set-Content "$root\Personal\todo.txt"

# Additional files at root
'System configuration and settings' | Set-Content "$root\README.md"
'Important passwords and credentials' | Set-Content "$root\credentials.txt"

Write-Host ""
Write-Host "Files created successfully!" -ForegroundColor Green
Write-Host ""

# Display summary
Write-Host "Directory Summary:" -ForegroundColor Cyan
$totalItems = (Get-ChildItem -Path $root -Recurse | Measure-Object).Count
$folders = (Get-ChildItem -Path $root -Recurse -Directory | Measure-Object).Count
$files = (Get-ChildItem -Path $root -Recurse -File | Measure-Object).Count

Write-Host "  Total items: $totalItems"
Write-Host "  Folders: $folders"
Write-Host "  Files: $files"
Write-Host ""

# Display folder structure
Write-Host "Folder structure:" -ForegroundColor Cyan
Get-ChildItem -Path $root -Directory | ForEach-Object {
    Write-Host "  [DIR] $($_.Name)"
    Get-ChildItem -Path $_.FullName -Directory | ForEach-Object {
        Write-Host "       [DIR] $($_.Name)"
    }
}

Write-Host ""
Write-Host "Sample files in each folder:" -ForegroundColor Cyan
Get-ChildItem -Path $root -Recurse -File | Select-Object -First 15 | ForEach-Object {
    $relativePath = $_.FullName -replace [regex]::Escape($root), ""
    Write-Host "  [FILE] $relativePath"
}
