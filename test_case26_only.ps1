# Test 26: Case conflict preserves newer content and creates conflict artifacts
$LeftPath = "C:\pdrive_local"
$RightPath = "p:\"

# Ensure sync_state.db is present for state tracking
if (-not (Test-Path ".\sync_state.db")) {
    # Run one empty sync to create the database
    python -m remote_office_sync.main
}

$test_name = "case_conflict_canonical"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"

# Clean up any existing test directories
if (Test-Path $test_left) {
    Remove-Item -Path $test_left -Recurse -Force
}
if (Test-Path $test_right) {
    Remove-Item -Path $test_right -Recurse -Force
}

# Create test directories
New-Item -ItemType Directory -Path $test_left -Force | Out-Null
New-Item -ItemType Directory -Path $test_right -Force | Out-Null

# Create files with different casing
$leftFile = "$test_left\CaseTest.txt"
$rightFile = "$test_right\casetest.txt"
"older-left-case" | Set-Content $leftFile
"NEW-RIGHT-CONTENT" | Set-Content $rightFile

# Ensure right side is newer than left for tie-breaking
(Get-Item $leftFile).LastWriteTime = (Get-Date).AddSeconds(-120)
(Get-Item $rightFile).LastWriteTime = (Get-Date).AddSeconds(-60)

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "INITIAL STATE:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Left file: $leftFile (older)" -ForegroundColor Yellow
Write-Host "  Content: $(Get-Content $leftFile -Raw)" -ForegroundColor Gray
Write-Host "  Mtime: $((Get-Item $leftFile).LastWriteTime)" -ForegroundColor Gray
Write-Host ""
Write-Host "Right file: $rightFile (newer)" -ForegroundColor Yellow
Write-Host "  Content: $(Get-Content $rightFile -Raw)" -ForegroundColor Gray
Write-Host "  Mtime: $((Get-Item $rightFile).LastWriteTime)" -ForegroundColor Gray

# Temporarily modify config for testing
$configPath = ".\config.yaml"
$originalConfig = Get-Content $configPath -Raw
# Convert Windows paths to forward slashes for YAML
$leftPathYaml = $LeftPath -replace '\\', '/'
$rightPathYaml = $RightPath -replace '\\', '/'
$tempConfig = $originalConfig `
    -replace "dry_run:\s*true", "dry_run: false" `
    -replace 'left_root:\s*"[^"]*"', "left_root: ""$leftPathYaml""" `
    -replace 'right_root:\s*"[^"]*"', "right_root: ""$rightPathYaml"""
Set-Content -Path $configPath -Value $tempConfig

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RUNNING FIRST SYNC..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
python -m remote_office_sync.main

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "RUNNING SECOND SYNC..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
python -m remote_office_sync.main

# Restore original config
Set-Content -Path $configPath -Value $originalConfig

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "CHECKING RESULTS..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$canonicalLeftPath = "$test_left\casetest.txt"
$canonicalRightPath = "$test_right\casetest.txt"

Write-Host "`nFILES IN LEFT DIRECTORY:" -ForegroundColor Yellow
Get-ChildItem -LiteralPath $test_left | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
    if ($_.Extension -eq ".txt") {
        Write-Host "    Content: $(Get-Content $_.FullName -Raw)" -ForegroundColor DarkGray
    }
}

Write-Host "`nFILES IN RIGHT DIRECTORY:" -ForegroundColor Yellow
Get-ChildItem -LiteralPath $test_right | ForEach-Object {
    Write-Host "  $($_.Name)" -ForegroundColor Gray
    if ($_.Extension -eq ".txt") {
        Write-Host "    Content: $(Get-Content $_.FullName -Raw)" -ForegroundColor DarkGray
    }
}

# Check results
$leftExists = Test-Path $canonicalLeftPath
$rightExists = Test-Path $canonicalRightPath
$contentMatches = $leftExists -and $rightExists -and
    ((Get-Content $canonicalLeftPath -Raw).Trim() -eq "NEW-RIGHT-CONTENT") -and
    ((Get-Content $canonicalRightPath -Raw).Trim() -eq "NEW-RIGHT-CONTENT")

$conflictLeft = Get-ChildItem -LiteralPath $test_left -Filter "CaseTest.CONFLICT*.txt" -ErrorAction SilentlyContinue
$conflictRight = Get-ChildItem -LiteralPath $test_right -Filter "CaseTest.CONFLICT*.txt" -ErrorAction SilentlyContinue
$conflictExists = ($conflictLeft.Count -gt 0) -and ($conflictRight.Count -gt 0)
$conflictContentOk = $conflictExists -and
    ((Get-Content $conflictLeft[0].FullName -Raw).Trim() -eq "older-left-case") -and
    ((Get-Content $conflictRight[0].FullName -Raw).Trim() -eq "older-left-case")

$leftNames = Get-ChildItem -LiteralPath $test_left | Select-Object -ExpandProperty Name
$rightNames = Get-ChildItem -LiteralPath $test_right | Select-Object -ExpandProperty Name
# Case-sensitive check - on Windows, CaseTest.txt and casetest.txt are different
$noOldCasingLeft = -not ($leftNames -ccontains "CaseTest.txt")
$noOldCasingRight = -not ($rightNames -ccontains "CaseTest.txt")

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "TEST RESULTS:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Write-Check {
    param($message, $passed)
    if ($passed) {
        Write-Host "  [OK] $message" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $message" -ForegroundColor Red
    }
}

Write-Check "Canonical file exists on left" $leftExists
Write-Check "Canonical file exists on right" $rightExists
Write-Check "Canonical content matches newer side" $contentMatches
Write-Check "Conflict files exist on both sides" $conflictExists
Write-Check "Conflict files contain older content" $conflictContentOk
Write-Check "Old casing removed on left" $noOldCasingLeft
Write-Check "Old casing removed on right" $noOldCasingRight

$allPassed = $leftExists -and $rightExists -and $contentMatches -and $conflictExists -and $conflictContentOk -and $noOldCasingLeft -and $noOldCasingRight

Write-Host ""
if ($allPassed) {
    Write-Host "TEST 26 PASSED" -ForegroundColor Green
} else {
    Write-Host "TEST 26 FAILED" -ForegroundColor Red
}

# Cleanup
Write-Host "`nCleaning up test directories..." -ForegroundColor Gray
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue
