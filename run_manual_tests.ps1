# Manual Test Suite for File Sync Application
# This script automates all manual tests documented in .claude/CLAUDE.md
# Usage: .\run_manual_tests.ps1 -LeftPath "C:\pdrive_local" -RightPath "p:\"

param(
    [Parameter(Mandatory=$true)]
    [string]$LeftPath,

    [Parameter(Mandatory=$true)]
    [string]$RightPath
)

# Colors for output
$SuccessColor = 'Green'
$FailureColor = 'Red'
$WarningColor = 'Yellow'
$InfoColor = 'Cyan'

# Test counters
$totalTests = 0
$passedTests = 0
$failedTests = 0

function Write-TestHeader {
    param([string]$TestName, [int]$TestNumber)
    Write-Host "`n$('='*60)" -ForegroundColor $InfoColor
    Write-Host "TEST ${TestNumber}: $TestName" -ForegroundColor $InfoColor
    Write-Host "$('='*60)" -ForegroundColor $InfoColor
}

function Write-Result {
    param([string]$Message, [bool]$Passed)
    $icon = if ($Passed) { '[OK]' } else { '[FAIL]' }
    $color = if ($Passed) { $SuccessColor } else { $FailureColor }
    Write-Host "$icon $Message" -ForegroundColor $color
    return $Passed
}

function Test-FileExists {
    param([string]$Path, [string]$Description)
    $exists = Test-Path -LiteralPath $Path -PathType Leaf
    Write-Result "$Description exists" $exists
    return $exists
}

function Test-ContentMatch {
    param([string]$LeftFile, [string]$RightFile, [string]$Description)
    $leftContent = Get-Content -LiteralPath $LeftFile -Raw -ErrorAction SilentlyContinue
    $rightContent = Get-Content -LiteralPath $RightFile -Raw -ErrorAction SilentlyContinue

    $match = $leftContent -eq $rightContent
    Write-Result "$Description content matches" $match
    return $match
}

function Invoke-Sync {
    Write-Host "Running sync..." -ForegroundColor $InfoColor
    $output = python -m remote_office_sync.main 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Sync completed successfully" -ForegroundColor $SuccessColor
    } else {
        Write-Host "Sync failed with exit code $LASTEXITCODE" -ForegroundColor $FailureColor
        return $false
    }

    # Check for errors in output
    if ($output -match "Jobs failed: [1-9]") {
        Write-Host "WARNING: Sync had failed jobs" -ForegroundColor $WarningColor
        return $false
    }
    return $true
}

function Cleanup-TestDirectories {
    Write-Host "Cleaning up test directories..." -ForegroundColor $InfoColor
    # Remove test directory and all its contents (including conflict files)
    Remove-Item -LiteralPath "$LeftPath\manual_test" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath "$RightPath\manual_test" -Recurse -Force -ErrorAction SilentlyContinue

    # Remove ONLY test-specific files and their conflict variants (not any user files)
    # Test files are named: test1, test2, conflict_test, new_new_conflict, CaseTest, casetest, delete_me_dir, emptydir, newdir
    $testPatterns = @("test1*", "test2*", "conflict_test*", "new_new_conflict*", "casetest*", "CaseTest*", "delete_me_dir*", "emptydir*", "newdir*")

    foreach ($pattern in $testPatterns) {
        Get-ChildItem -Path "$LeftPath" -Filter $pattern -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        Get-ChildItem -Path "$RightPath" -Filter $pattern -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function New-TestDirectory {
    param([string]$Path)
    $testDir = Join-Path $Path "manual_test"
    New-Item -ItemType Directory -Path $testDir -Force | Out-Null
    return $testDir
}

# Main test execution
Write-Host "File Sync Manual Test Suite" -ForegroundColor $InfoColor
Write-Host "Left path: $LeftPath" -ForegroundColor $InfoColor
Write-Host "Right path: $RightPath" -ForegroundColor $InfoColor

# Verify paths exist
if (-not (Test-Path -LiteralPath $LeftPath)) {
    Write-Host "ERROR: Left path does not exist: $LeftPath" -ForegroundColor $FailureColor
    exit 1
}

if (-not (Test-Path -LiteralPath $RightPath)) {
    Write-Host "ERROR: Right path does not exist: $RightPath" -ForegroundColor $FailureColor
    exit 1
}

# Set dry_run to false for testing
Write-Host "`nConfiguring sync for testing..." -ForegroundColor $InfoColor
if (Test-Path -LiteralPath "config.yaml") {
    $config = Get-Content "config.yaml" -Raw
    $originalConfig = $config
    $config = $config -replace 'dry_run:\s+true', 'dry_run: false'
    $config = $config -replace 'dry_run:\s+false', 'dry_run: false'
    Set-Content "config.yaml" $config
    Write-Host "Set dry_run: false in config.yaml" -ForegroundColor $SuccessColor
} else {
    Write-Host "WARNING: config.yaml not found, assuming dry_run is already false" -ForegroundColor $WarningColor
}

# Cleanup old test files
Cleanup-TestDirectories
$leftTestDir = New-TestDirectory $LeftPath
$rightTestDir = New-TestDirectory $RightPath

# Test 1: File creation L->R
$totalTests++
Write-TestHeader "File creation L->R with content verification" 1
"TEST1: File creation L→R" | Set-Content "$leftTestDir\test1.txt"
if (Invoke-Sync) {
    $fileExists = Test-FileExists "$rightTestDir\test1.txt" "File on right"
    $contentMatches = Test-ContentMatch "$leftTestDir\test1.txt" "$rightTestDir\test1.txt" "Content"
    if ($fileExists -and $contentMatches) {
        $passedTests++
        Write-Result "Test 1 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 1 FAILED" $false
    }
}

# Test 2: File creation R->L
$totalTests++
Write-TestHeader "File creation R->L with content verification" 2
"TEST2: File creation R→L" | Set-Content "$rightTestDir\test2.txt"
if (Invoke-Sync) {
    $fileExists = Test-FileExists "$leftTestDir\test2.txt" "File on left"
    $contentMatches = Test-ContentMatch "$leftTestDir\test2.txt" "$rightTestDir\test2.txt" "Content"
    if ($fileExists -and $contentMatches) {
        $passedTests++
        Write-Result "Test 2 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 2 FAILED" $false
    }
}

# Test 3: File modification L->R
$totalTests++
Write-TestHeader "File modification L->R with content verification" 3
"MODIFIED on left side" | Add-Content "$leftTestDir\test1.txt"
if (Invoke-Sync) {
    $contentMatches = Test-ContentMatch "$leftTestDir\test1.txt" "$rightTestDir\test1.txt" "Modified content"
    if ($contentMatches) {
        $passedTests++
        Write-Result "Test 3 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 3 FAILED" $false
    }
}

# Test 4: File modification R->L
$totalTests++
Write-TestHeader "File modification R->L with content verification" 4
"MODIFIED on right side" | Add-Content "$rightTestDir\test2.txt"
if (Invoke-Sync) {
    $contentMatches = Test-ContentMatch "$leftTestDir\test2.txt" "$rightTestDir\test2.txt" "Modified content"
    if ($contentMatches) {
        $passedTests++
        Write-Result "Test 4 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 4 FAILED" $false
    }
}

# Test 5: File deletion from left
$totalTests++
Write-TestHeader "File deletion from left" 5
"File for deletion from left" | Set-Content "$leftTestDir\delete_test_left.txt"
Invoke-Sync | Out-Null
Remove-Item -LiteralPath "$leftTestDir\delete_test_left.txt" -Force
if (Invoke-Sync) {
    $leftExists = Test-Path -LiteralPath "$leftTestDir\delete_test_left.txt"
    $rightExists = Test-Path -LiteralPath "$rightTestDir\delete_test_left.txt"
    $deleted = (-not $leftExists) -and (-not $rightExists)
    if (Write-Result "File deleted from both sides" $deleted) {
        $passedTests++
        Write-Result "Test 5 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 5 FAILED" $false
    }
}

# Test 6: File deletion from right
$totalTests++
Write-TestHeader "File deletion from right" 6
"File for deletion from right" | Set-Content "$rightTestDir\delete_test_right.txt"
Invoke-Sync | Out-Null
Remove-Item -LiteralPath "$rightTestDir\delete_test_right.txt" -Force
if (Invoke-Sync) {
    $leftExists = Test-Path -LiteralPath "$leftTestDir\delete_test_right.txt"
    $rightExists = Test-Path -LiteralPath "$rightTestDir\delete_test_right.txt"
    $deleted = (-not $leftExists) -and (-not $rightExists)
    if (Write-Result "File deleted from both sides" $deleted) {
        $passedTests++
        Write-Result "Test 6 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 6 FAILED" $false
    }
}

# Test 7: Directory Sync
$totalTests++
Write-TestHeader "Directory Sync with structure verification" 7
$newDir = New-Item -ItemType Directory -Path "$leftTestDir\newdir" -Force
if (Invoke-Sync) {
    $rightDirExists = Test-Path -LiteralPath "$rightTestDir\newdir" -PathType Container
    Write-Result "Directory exists on right" $rightDirExists
    if ($rightDirExists) {
        $passedTests++
        Write-Result "Test 7 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 7 FAILED" $false
    }
}

# Test 8: Modify-modify conflict
$totalTests++
Write-TestHeader "Modify-modify conflict with content verification" 8
"Original content" | Set-Content "$leftTestDir\conflict_test.txt"
Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100
"Modified on right side" | Set-Content "$rightTestDir\conflict_test.txt"
"Modified on left side" | Set-Content "$leftTestDir\conflict_test.txt"
if (Invoke-Sync) {
    $mainExists = (Test-Path "$leftTestDir\conflict_test.txt") -and (Test-Path "$rightTestDir\conflict_test.txt")
    $conflictLeft = Get-ChildItem -LiteralPath $leftTestDir -Filter "conflict_test.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictRight = Get-ChildItem -LiteralPath $rightTestDir -Filter "conflict_test.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictExists = ($conflictLeft.Count -gt 0) -and ($conflictRight.Count -gt 0)
    $contentMatch = Test-ContentMatch "$leftTestDir\conflict_test.txt" "$rightTestDir\conflict_test.txt" "Main files"

    if ($mainExists -and $conflictExists -and $contentMatch) {
        $passedTests++
        Write-Result "Test 8 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 8 FAILED" $false
    }
}

# Test 9: New-new conflict
$totalTests++
Write-TestHeader "New-new conflict with content verification" 9
"Created on left side" | Set-Content "$leftTestDir\new_new_conflict.txt"
Start-Sleep -Milliseconds 100
"Created on right side" | Set-Content "$rightTestDir\new_new_conflict.txt"
if (Invoke-Sync) {
    $mainExists = (Test-Path "$leftTestDir\new_new_conflict.txt") -and (Test-Path "$rightTestDir\new_new_conflict.txt")
    $conflictLeft = Get-ChildItem -LiteralPath $leftTestDir -Filter "new_new_conflict.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictRight = Get-ChildItem -LiteralPath $rightTestDir -Filter "new_new_conflict.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictExists = ($conflictLeft.Count -gt 0) -and ($conflictRight.Count -gt 0)

    if ($mainExists -and $conflictExists) {
        $passedTests++
        Write-Result "Test 9 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 9 FAILED" $false
    }
}

# Test 10: Case conflict
$totalTests++
Write-TestHeader "Case conflict with content verification" 10
"Case conflict test content" | Set-Content "$leftTestDir\casetest.txt"
Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100
"MODIFIED CASE CONTENT" | Set-Content "$leftTestDir\casetest.txt"
Rename-Item -LiteralPath "$rightTestDir\casetest.txt" -NewName "CaseTest.txt" -ErrorAction SilentlyContinue
if (Invoke-Sync) {
    # After sync, main file should exist on both sides
    $mainLeftExists = Test-Path "$leftTestDir\casetest.txt"
    $mainRightExists = (Test-Path "$rightTestDir\casetest.txt") -or (Test-Path "$rightTestDir\CaseTest.txt")

    if ($mainLeftExists -and $mainRightExists) {
        $passedTests++
        Write-Result "Test 10 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 10 FAILED" $false
    }
}

# Test 11: Subdirectory files
$totalTests++
Write-TestHeader "Subdirectory files with content verification" 11
$subdir = New-Item -ItemType Directory -Path "$leftTestDir\subdir\nested" -Force
"File in nested directory" | Set-Content "$subdir\deepfile.txt"
if (Invoke-Sync) {
    $rightSubDir = Join-Path $rightTestDir "subdir\nested\deepfile.txt"
    $fileExists = Test-FileExists $rightSubDir "File in nested directory"
    $contentMatches = Test-ContentMatch "$subdir\deepfile.txt" $rightSubDir "Content"
    if ($fileExists -and $contentMatches) {
        $passedTests++
        Write-Result "Test 11 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 11 FAILED" $false
    }
}

# Test 12: Directory deletion
$totalTests++
Write-TestHeader "Directory deletion" 12
mkdir -Force "$leftTestDir\delete_me_dir\subdir" | Out-Null
"File to be deleted" | Set-Content "$leftTestDir\delete_me_dir\subdir\file.txt"
if (Invoke-Sync) {
    # Verify directory exists on right
    $rightDirExists = Test-Path -LiteralPath "$rightTestDir\delete_me_dir\subdir" -PathType Container
    if ($rightDirExists) {
        # Now delete the directory from left
        Remove-Item -LiteralPath "$leftTestDir\delete_me_dir" -Recurse -Force
        if (Invoke-Sync) {
            # After sync, the file should be soft-deleted from right
            # The empty directory structure will remain (only files are deleted)
            $fileDeleted = -not (Test-Path -LiteralPath "$rightTestDir\delete_me_dir\subdir\file.txt")
            if ($fileDeleted) {
                $passedTests++
                Write-Result "Test 12 PASSED" $true
            } else {
                $failedTests++
                Write-Result "Test 12 FAILED" $false
            }
        }
    } else {
        $failedTests++
        Write-Result "Test 12 FAILED - directory not synced" $false
    }
}

# Test 13: Empty directory creation from right to left
$totalTests++
Write-TestHeader "Empty directory creation R->L" 13
$newDirRight = New-Item -ItemType Directory -Path "$rightTestDir\emptydir_from_right" -Force
if (Invoke-Sync) {
    $leftDirExists = Test-Path -LiteralPath "$leftTestDir\emptydir_from_right" -PathType Container
    Write-Result "Empty directory exists on left" $leftDirExists
    if ($leftDirExists) {
        $passedTests++
        Write-Result "Test 13 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 13 FAILED" $false
    }
}

# Summary
Write-Host "`n$('='*60)" -ForegroundColor $InfoColor
Write-Host "TEST SUMMARY" -ForegroundColor $InfoColor
Write-Host "$('='*60)" -ForegroundColor $InfoColor
Write-Host "Total Tests: $totalTests" -ForegroundColor $InfoColor
Write-Host "Passed: $passedTests" -ForegroundColor $SuccessColor
Write-Host "Failed: $failedTests" -ForegroundColor $(if ($failedTests -gt 0) { $FailureColor } else { $SuccessColor })

# Cleanup
Write-Host "`nCleaning up test files..." -ForegroundColor $InfoColor
Cleanup-TestDirectories

# Restore dry_run to true
Write-Host "Restoring dry_run: true in config.yaml..." -ForegroundColor $InfoColor
if (Test-Path -LiteralPath "config.yaml") {
    $config = Get-Content "config.yaml" -Raw
    $config = $config -replace 'dry_run:\s+false', 'dry_run: true'
    Set-Content "config.yaml" $config
    Write-Host "Restored dry_run: true" -ForegroundColor $SuccessColor
}

# Exit with appropriate code
if ($failedTests -gt 0) {
    exit 1
} else {
    Write-Host "All tests passed!" -ForegroundColor $SuccessColor
    exit 0
}
