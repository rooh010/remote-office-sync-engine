# Test 26 with debug output
$LeftPath = "C:\pdrive_local"
$RightPath = "p:\"

$test_name = "case_conflict_canonical"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"

# Clean up
if (Test-Path $test_left) { Remove-Item -Path $test_left -Recurse -Force }
if (Test-Path $test_right) { Remove-Item -Path $test_right -Recurse -Force }

# Create test directories
New-Item -ItemType Directory -Path $test_left -Force | Out-Null
New-Item -ItemType Directory -Path $test_right -Force | Out-Null

# Create files with different casing
$leftFile = "$test_left\CaseTest.txt"
$rightFile = "$test_right\casetest.txt"
"older-left-case" | Set-Content $leftFile
"NEW-RIGHT-CONTENT" | Set-Content $rightFile

# Ensure right side is newer
(Get-Item $leftFile).LastWriteTime = (Get-Date).AddSeconds(-120)
(Get-Item $rightFile).LastWriteTime = (Get-Date).AddSeconds(-60)

Write-Host "INITIAL STATE:" -ForegroundColor Cyan
Write-Host "Left: $leftFile" -ForegroundColor Yellow
Get-Content $leftFile
Write-Host "Right: $rightFile" -ForegroundColor Yellow
Get-Content $rightFile

# Temporarily modify config
$configPath = ".\config.yaml"
$originalConfig = Get-Content $configPath -Raw
$tempConfig = $originalConfig `
    -replace "dry_run:\s*true", "dry_run: false" `
    -replace 'left_root:\s*"[^"]*"', "left_root: ""$LeftPath""" `
    -replace 'right_root:\s*"[^"]*"', "right_root: ""$RightPath"""
Set-Content -Path $configPath -Value $tempConfig

Write-Host "`nRUNNING FIRST SYNC..." -ForegroundColor Cyan
python -m remote_office_sync.main 2>&1 | Select-String -Pattern "Case conflict|CASE_CONFLICT|case_conflict_canonical"

Write-Host "`nAFTER FIRST SYNC:" -ForegroundColor Cyan
Write-Host "Files in left:" -ForegroundColor Yellow
Get-ChildItem -Path $test_left | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host "Files in right:" -ForegroundColor Yellow
Get-ChildItem -Path $test_right | ForEach-Object { Write-Host "  $($_.Name)" }

# Restore config
Set-Content -Path $configPath -Value $originalConfig

# Cleanup
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue
