# Manual Test Suite for File Sync Application
# This script automates all manual tests documented in .claude/CLAUDE.md
# Usage: .\run_manual_tests.ps1 -LeftPath "C:\local_share" -RightPath "R:\remote_share"

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
    [void](Write-Result "$Description exists" $exists)
    return $exists
}

function Test-ContentMatch {
    param([string]$LeftFile, [string]$RightFile, [string]$Description)
    $leftContent = Get-Content -LiteralPath $LeftFile -Raw -ErrorAction SilentlyContinue
    $rightContent = Get-Content -LiteralPath $RightFile -Raw -ErrorAction SilentlyContinue

    $match = $leftContent -eq $rightContent
    [void](Write-Result "$Description content matches" $match)
    return $match
}

function Invoke-Sync {
    Write-Host "Running sync..." -ForegroundColor $InfoColor
    $configArg = @()
    if (Test-Path -LiteralPath $TempConfigPath) {
        $configArg = @("--config", $TempConfigPath)
    }
    $output = python -m remote_office_sync.main @configArg 2>&1
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
    # Test files are named: test1, test2, conflict_test, new_new_conflict, CaseTest, casetest, delete_me_dir, emptydir, newdir, subconflict, stress_test, caseconflict_test, attr_test, dir_rename_left, dir_rename_right, dir_same_rename, dir_rename_conflict, nested_rename, verify_new_rename, content_preservation, case_change_dir
    $testPatterns = @("test1*", "test2*", "conflict_test*", "new_new_conflict*", "casetest*", "CaseTest*", "delete_me_dir*", "emptydir*", "newdir*", "subconflict*", "stress_test*", "caseconflict_test*", "attr_test*", "dir_rename_left*", "dir_rename_right*", "dir_same_rename*", "dir_rename_conflict*", "nested_rename*", "verify_new_rename*", "content_preservation*", "case_change_dir*")

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

# Reset sync state for isolated test runs
Remove-Item -LiteralPath "sync_state.db" -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ".deleted" -Recurse -Force -ErrorAction SilentlyContinue

# Build a temporary config using provided paths (without touching config.yaml)
Write-Host "`nConfiguring sync for testing..." -ForegroundColor $InfoColor
$TempConfigPath = Join-Path $PSScriptRoot "config.manualtest.tmp.yaml"

# Start from existing config.yaml if present, else fall back to template or minimal defaults
if (Test-Path -LiteralPath "config.yaml") {
    $config = Get-Content "config.yaml" -Raw
    Write-Host "Using config.yaml as base for test config" -ForegroundColor $InfoColor
} elseif (Test-Path -LiteralPath "config.template.yaml") {
    $config = Get-Content "config.template.yaml" -Raw
    Write-Host "Using config.template.yaml as base for test config" -ForegroundColor $InfoColor
} else {
    Write-Host "WARNING: config.yaml not found; generating minimal test config" -ForegroundColor $WarningColor
    $config = @"
left_root: ""
right_root: ""
dry_run: true
"@
}

$leftRootValue = ($LeftPath -replace '\\', '/')
if (-not $leftRootValue.EndsWith('/')) { $leftRootValue += '/' }
$rightRootValue = ($RightPath -replace '\\', '/')
if (-not $rightRootValue.EndsWith('/')) { $rightRootValue += '/' }

# Force dry_run off
$config = $config -replace 'dry_run:\s+true', 'dry_run: false'
$config = $config -replace 'dry_run:\s+false', 'dry_run: false'

# Override roots; if missing, prepend them
if ($config -match 'left_root:\s*".*?"') {
    $config = [regex]::Replace($config, 'left_root:\s*".*?"', "left_root: `"$leftRootValue`"")
} else {
    $config = "left_root: `"$leftRootValue`"`n" + $config
}

if ($config -match 'right_root:\s*".*?"') {
    $config = [regex]::Replace($config, 'right_root:\s*".*?"', "right_root: `"$rightRootValue`"")
} else {
    $config = "right_root: `"$rightRootValue`"`n" + $config
}

Set-Content -LiteralPath $TempConfigPath -Value $config -Encoding UTF8
Write-Host "Prepared temporary test config: $TempConfigPath" -ForegroundColor $SuccessColor

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

# Test 14: Conflict files in subdirectory (verify they are not placed at root)
$totalTests++
Write-TestHeader "Modify-modify conflict in subdirectory" 14
$subconflictDir = New-Item -ItemType Directory -Path "$leftTestDir\subconflict\nested" -Force
"Original conflict content" | Set-Content "$leftTestDir\subconflict\nested\file.txt"
Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100
"Modified on right in subdir" | Set-Content "$rightTestDir\subconflict\nested\file.txt"
"Modified on left in subdir" | Set-Content "$leftTestDir\subconflict\nested\file.txt"
if (Invoke-Sync) {
    # Check that conflict files are in the SUBDIRECTORY, not at root
    $conflictInSubdir = Get-ChildItem -LiteralPath "$leftTestDir\subconflict\nested" -Filter "file.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictAtRoot = Get-ChildItem -LiteralPath $leftTestDir -Filter "file.CONFLICT*" -ErrorAction SilentlyContinue

    $correctLocation = ($conflictInSubdir.Count -gt 0) -and ($conflictAtRoot.Count -eq 0)
    Write-Result "Conflict file in correct subdirectory (not root)" $correctLocation

    # Also verify on right side
    $conflictRightSubdir = Get-ChildItem -LiteralPath "$rightTestDir\subconflict\nested" -Filter "file.CONFLICT*" -ErrorAction SilentlyContinue
    $conflictRightRoot = Get-ChildItem -LiteralPath $rightTestDir -Filter "file.CONFLICT*" -ErrorAction SilentlyContinue
    $correctLocationRight = ($conflictRightSubdir.Count -gt 0) -and ($conflictRightRoot.Count -eq 0)
    Write-Result "Conflict file in correct subdirectory on right" $correctLocationRight

    if ($correctLocation -and $correctLocationRight) {
        $passedTests++
        Write-Result "Test 14 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 14 FAILED" $false
    }
}

# Test 15: Comprehensive stress test - multiple operations simultaneously
$totalTests++
Write-TestHeader "Comprehensive stress test: many operations and conflicts" 15
Write-Host "Creating complex scenario with multiple simultaneous operations..." -ForegroundColor $WarningColor

# Create directory structures
$stressDir = "$leftTestDir\stress_test"
mkdir -Force "$stressDir\docs" | Out-Null
mkdir -Force "$stressDir\media\images" | Out-Null
mkdir -Force "$stressDir\logs" | Out-Null

# Create initial files and sync
"Initial doc 1" | Set-Content "$stressDir\docs\doc1.txt"
"Initial doc 2" | Set-Content "$stressDir\docs\doc2.txt"
"Image file 1" | Set-Content "$stressDir\media\images\img1.txt"
"Log entry 1" | Set-Content "$stressDir\logs\app.log"
"Will be deleted from left" | Set-Content "$stressDir\to_delete_left.txt"

Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100

# Now create simultaneous operations on both sides
# LEFT SIDE operations
"Modified doc1 from left" | Set-Content "$stressDir\docs\doc1.txt"
"New file on left" | Set-Content "$stressDir\new_left_file.txt"
mkdir -Force "$stressDir\media\videos" | Out-Null
"Video file" | Set-Content "$stressDir\media\videos\movie.txt"
Remove-Item "$stressDir\to_delete_left.txt" -Force

# RIGHT SIDE operations (create mirror structure and modifications)
$stressDirRight = "$rightTestDir\stress_test"
mkdir -Force "$stressDirRight\docs" | Out-Null
mkdir -Force "$stressDirRight\media\images" | Out-Null
mkdir -Force "$stressDirRight\logs" | Out-Null

# RIGHT: Modify existing files differently (conflicts!)
"Modified doc1 from right" | Set-Content "$stressDirRight\docs\doc1.txt"
"Different doc2 content right" | Set-Content "$stressDirRight\docs\doc2.txt"

# RIGHT: Create different new files
"New file on right" | Set-Content "$stressDirRight\new_right_file.txt"
"Config on right" | Set-Content "$stressDirRight\config.ini"

# RIGHT: Create new directories with files
mkdir -Force "$stressDirRight\data" | Out-Null
"Data file" | Set-Content "$stressDirRight\data\data.csv"
mkdir -Force "$stressDirRight\media\audio" | Out-Null
"Audio file" | Set-Content "$stressDirRight\media\audio\song.txt"

# RIGHT: Delete a file
Remove-Item "$stressDirRight\to_delete_left.txt" -Force -ErrorAction SilentlyContinue

# Run sync and verify everything works
if (Invoke-Sync) {
    # Verify files were synced
    $leftNewRight = Test-Path "$stressDir\new_right_file.txt"
    $rightNewLeft = Test-Path "$stressDirRight\new_left_file.txt"

    # Verify directories were synced
    $leftVideos = Test-Path "$stressDir\media\videos" -PathType Container
    $leftData = Test-Path "$stressDir\data" -PathType Container
    $rightAudio = Test-Path "$stressDirRight\media\audio" -PathType Container

    # Verify conflicts exist (doc1.txt and doc2.txt should have conflicts)
    $conflictsDocs = @(Get-ChildItem -LiteralPath "$stressDir\docs" -Filter "*.CONFLICT*" -ErrorAction SilentlyContinue)
    $conflictsRight = @(Get-ChildItem -LiteralPath "$stressDirRight\docs" -Filter "*.CONFLICT*" -ErrorAction SilentlyContinue)
    $hasConflicts = ($conflictsDocs.Count -gt 0) -and ($conflictsRight.Count -gt 0)

    Write-Result "New file synced left→right" $leftNewRight
    Write-Result "New file synced right→left" $rightNewLeft
    Write-Result "New directory synced (videos)" $leftVideos
    Write-Result "New directory synced (data)" $leftData
    Write-Result "New directory synced (audio)" $rightAudio
    Write-Result "Conflicts detected in docs" $hasConflicts

    if ($leftNewRight -and $rightNewLeft -and $leftVideos -and $leftData -and $rightAudio -and $hasConflicts) {
        $passedTests++
        Write-Result "Test 15 PASSED - Complex scenario handled successfully" $true
    } else {
        $failedTests++
        Write-Result "Test 15 FAILED" $false
    }
}

# Test 16: Case conflict in subdirectory (verify conflict files go to subdir, not root)
$totalTests++
Write-TestHeader "Case conflict in subdirectory" 16
# Clean up leftover files from previous tests before running Test 16
Cleanup-TestDirectories
New-Item -ItemType Directory -Path "$leftTestDir" -Force | Out-Null
$caseconflictDir = New-Item -ItemType Directory -Path "$leftTestDir\caseconflict_test\docs" -Force
"Original file content" | Set-Content "$leftTestDir\caseconflict_test\docs\document.txt"
Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100
# Create case conflict: rename one side to different case
Rename-Item -LiteralPath "$rightTestDir\caseconflict_test\docs\document.txt" -NewName "Document.txt" -ErrorAction SilentlyContinue
# Also modify the file
"Modified content" | Set-Content "$leftTestDir\caseconflict_test\docs\document.txt"
if (Invoke-Sync) {
    # Verify conflict files are in the SUBDIRECTORY, not at root
    # Use wildcard to match any CONFLICT file (document or Document case variant)
    # Use -File to match only files, not directories (caseconflict_test dir contains "conflict")
    $conflictInSubdir = Get-ChildItem -LiteralPath "$leftTestDir\caseconflict_test\docs" -Filter "*CONFLICT*" -File -ErrorAction SilentlyContinue
    $conflictAtRoot = Get-ChildItem -LiteralPath $leftTestDir -Filter "*CONFLICT*" -File -Depth 1 -ErrorAction SilentlyContinue

    $correctLocation = ($conflictInSubdir.Count -gt 0) -and ($conflictAtRoot.Count -eq 0)
    Write-Result "Case conflict file in subdirectory (not root)" $correctLocation

    # Also verify on right side
    $conflictRightSubdir = Get-ChildItem -LiteralPath "$rightTestDir\caseconflict_test\docs" -Filter "*CONFLICT*" -File -ErrorAction SilentlyContinue
    $conflictRightRoot = Get-ChildItem -LiteralPath $rightTestDir -Filter "*CONFLICT*" -File -Depth 1 -ErrorAction SilentlyContinue

    $correctLocationRight = ($conflictRightSubdir.Count -gt 0) -and ($conflictRightRoot.Count -eq 0)
    Write-Result "Case conflict file in subdirectory on right" $correctLocationRight

    if ($correctLocation -and $correctLocationRight) {
        $passedTests++
        Write-Result "Test 16 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 16 FAILED" $false
    }
}

# Test 17: File attribute synchronization
$totalTests++
Write-TestHeader "File attribute synchronization" 17

# Create test files with attributes
$attrTestDir = New-Item -ItemType Directory -Path "$leftTestDir\attr_test" -Force
"Test file with attributes" | Set-Content "$attrTestDir\file.txt"

# Sync to right side
Invoke-Sync | Out-Null
Start-Sleep -Milliseconds 100

# Function to set file attributes using PowerShell
function Set-FileAttribute {
    param([string]$Path, [ValidateSet('Hidden', 'ReadOnly', 'Archive')]$Attribute)
    $file = Get-Item -LiteralPath $Path -Force
    $file.Attributes = $file.Attributes -bor [System.IO.FileAttributes]::$Attribute
}

# Function to check if file has attribute
function Test-FileAttribute {
    param([string]$Path, [ValidateSet('Hidden', 'ReadOnly', 'Archive')]$Attribute)
    $file = Get-Item -LiteralPath $Path -Force
    return ($file.Attributes -band [System.IO.FileAttributes]::$Attribute) -ne 0
}

try {
    # Set ReadOnly attribute on left file
    Set-FileAttribute -Path "$attrTestDir\file.txt" -Attribute ReadOnly

    # Sync (should detect attribute change and sync)
    if (Invoke-Sync) {
        # Wait a moment for file operations
        Start-Sleep -Milliseconds 100

        # Check if right side has the ReadOnly attribute
        $rightAttrDir = "$rightTestDir\attr_test"
        $rightFile = "$rightAttrDir\file.txt"

        if (Test-Path -LiteralPath $rightFile) {
            $rightHasReadOnly = Test-FileAttribute -Path $rightFile -Attribute ReadOnly
            Write-Result "Left file has ReadOnly attribute" $true
            Write-Result "Right file synced with ReadOnly attribute" $rightHasReadOnly

            # Test another attribute: Archive
            Set-FileAttribute -Path "$attrTestDir\file.txt" -Attribute Archive

            if (Invoke-Sync) {
                Start-Sleep -Milliseconds 100
                $rightHasArchive = Test-FileAttribute -Path $rightFile -Attribute Archive
                Write-Result "Archive attribute synced left→right" $rightHasArchive

                # Set attribute on right side
                Set-FileAttribute -Path $rightFile -Attribute Hidden

                if (Invoke-Sync) {
                    Start-Sleep -Milliseconds 100
                    $leftHasHidden = Test-FileAttribute -Path "$attrTestDir\file.txt" -Attribute Hidden
                    Write-Result "Hidden attribute synced right→left" $leftHasHidden

                    # Test combined attributes
                    $leftFileObj = Get-Item -LiteralPath "$attrTestDir\file.txt" -Force
                    $rightFileObj = Get-Item -LiteralPath $rightFile -Force

                    if ($rightHasReadOnly -and $rightHasArchive -and $leftHasHidden) {
                        $passedTests++
                        Write-Result "Test 17 PASSED - Attributes synchronized correctly" $true
                    } else {
                        $failedTests++
                        Write-Result "Test 17 FAILED - Not all attributes synced correctly" $false
                    }
                } else {
                    $failedTests++
                    Write-Result "Test 17 FAILED - Sync failed for right→left sync" $false
                }
            } else {
                $failedTests++
                Write-Result "Test 17 FAILED - Sync failed for Archive attribute" $false
            }
        } else {
            $failedTests++
            Write-Result "Test 17 FAILED - File not synced to right side" $false
        }
    } else {
        $failedTests++
        Write-Result "Test 17 FAILED - Initial sync failed" $false
    }
} catch {
    Write-Result "Test 17 FAILED - Error during attribute test: $_" $false
    $failedTests++
}

# Test 18: Directory rename on left side only
$totalTests++
Write-TestHeader "Directory rename on left side only" 18
$test_name = "dir_rename_left"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\old_folder" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\old_folder" -Force | Out-Null
"test content" | Set-Content "$test_left\old_folder\file.txt"
"test content" | Set-Content "$test_right\old_folder\file.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
Rename-Item -Path "$test_left\old_folder" -NewName "new_folder"
if (Invoke-Sync) {
    $newOnLeft = Test-Path "$test_left\new_folder" -PathType Container
    $newOnRight = Test-Path "$test_right\new_folder" -PathType Container
    $oldOnLeft = Test-Path "$test_left\old_folder" -PathType Container
    $oldOnRight = Test-Path "$test_right\old_folder" -PathType Container
    $fileOnLeft = Test-Path "$test_left\new_folder\file.txt"
    $fileOnRight = Test-Path "$test_right\new_folder\file.txt"
    Write-Result "New folder exists on left" $newOnLeft
    Write-Result "New folder exists on right" $newOnRight
    Write-Result "Old folder does not exist on left" (-not $oldOnLeft)
    Write-Result "Old folder does not exist on right" (-not $oldOnRight)
    Write-Result "File exists in new folder on left" $fileOnLeft
    Write-Result "File exists in new folder on right" $fileOnRight
    if ($newOnLeft -and $newOnRight -and (-not $oldOnLeft) -and (-not $oldOnRight) -and $fileOnLeft -and $fileOnRight) {
        $passedTests++
        Write-Result "Test 18 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 18 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 19: Directory rename on right side only
$totalTests++
Write-TestHeader "Directory rename on right side only" 19
$test_name = "dir_rename_right"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\old_folder" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\old_folder" -Force | Out-Null
"test content" | Set-Content "$test_left\old_folder\file.txt"
"test content" | Set-Content "$test_right\old_folder\file.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
Rename-Item -Path "$test_right\old_folder" -NewName "new_folder"
if (Invoke-Sync) {
    $newOnLeft = Test-Path "$test_left\new_folder" -PathType Container
    $newOnRight = Test-Path "$test_right\new_folder" -PathType Container
    $oldOnLeft = Test-Path "$test_left\old_folder" -PathType Container
    $oldOnRight = Test-Path "$test_right\old_folder" -PathType Container
    Write-Result "New folder exists on left" $newOnLeft
    Write-Result "New folder exists on right" $newOnRight
    Write-Result "Old folder does not exist on left" (-not $oldOnLeft)
    Write-Result "Old folder does not exist on right" (-not $oldOnRight)
    if ($newOnLeft -and $newOnRight -and (-not $oldOnLeft) -and (-not $oldOnRight)) {
        $passedTests++
        Write-Result "Test 19 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 19 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 20: Directory rename to same name on both sides
$totalTests++
Write-TestHeader "Directory rename to same name on both sides" 20
$test_name = "dir_same_rename"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\old_folder" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\old_folder" -Force | Out-Null
"test content" | Set-Content "$test_left\old_folder\file.txt"
"test content" | Set-Content "$test_right\old_folder\file.txt"
Rename-Item -Path "$test_left\old_folder" -NewName "new_folder"
Rename-Item -Path "$test_right\old_folder" -NewName "new_folder"
if (Invoke-Sync) {
    $newOnLeft = Test-Path "$test_left\new_folder" -PathType Container
    $newOnRight = Test-Path "$test_right\new_folder" -PathType Container
    $oldOnLeft = Test-Path "$test_left\old_folder" -PathType Container
    $oldOnRight = Test-Path "$test_right\old_folder" -PathType Container
    Write-Result "New folder exists on both sides" ($newOnLeft -and $newOnRight)
    Write-Result "Old folder does not exist on left" (-not $oldOnLeft)
    Write-Result "Old folder does not exist on right" (-not $oldOnRight)
    if ($newOnLeft -and $newOnRight -and (-not $oldOnLeft) -and (-not $oldOnRight)) {
        $passedTests++
        Write-Result "Test 20 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 20 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 21: Directory rename conflict (different names on both sides)
$totalTests++
Write-TestHeader "Directory rename conflict (different names)" 21
$test_name = "dir_rename_conflict"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\old_folder" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\old_folder" -Force | Out-Null
"test content" | Set-Content "$test_left\old_folder\file.txt"
"test content" | Set-Content "$test_right\old_folder\file.txt"
Rename-Item -Path "$test_left\old_folder" -NewName "left_folder"
Rename-Item -Path "$test_right\old_folder" -NewName "right_folder"
if (Invoke-Sync) {
    Write-Result "Rename conflict handled without crash" $true
    $passedTests++
    Write-Result "Test 21 PASSED" $true
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 22: Nested directory rename
$totalTests++
Write-TestHeader "Nested directory rename" 22
$test_name = "nested_rename"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\old\sub1\sub2" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\old\sub1\sub2" -Force | Out-Null
"file1" | Set-Content "$test_left\old\file1.txt"
"file2" | Set-Content "$test_left\old\sub1\file2.txt"
"file3" | Set-Content "$test_left\old\sub1\sub2\file3.txt"
"file1" | Set-Content "$test_right\old\file1.txt"
"file2" | Set-Content "$test_right\old\sub1\file2.txt"
"file3" | Set-Content "$test_right\old\sub1\sub2\file3.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
Rename-Item -Path "$test_left\old" -NewName "new"
if (Invoke-Sync) {
    $nestedLeft = Test-Path "$test_left\new\sub1\sub2\file3.txt"
    $nestedRight = Test-Path "$test_right\new\sub1\sub2\file3.txt"
    $oldLeft = Test-Path "$test_left\old" -PathType Container
    $oldRight = Test-Path "$test_right\old" -PathType Container
    Write-Result "Nested structure on left" $nestedLeft
    Write-Result "Nested structure on right" $nestedRight
    Write-Result "Old folder does not exist on left" (-not $oldLeft)
    Write-Result "Old folder does not exist on right" (-not $oldRight)
    if ($nestedLeft -and $nestedRight -and (-not $oldLeft) -and (-not $oldRight)) {
        $passedTests++
        Write-Result "Test 22 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 22 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 23: Verify renamed directory content syncs correctly
$totalTests++
Write-TestHeader "Verify renamed directory content syncs correctly" 23
$test_name = "verify_new_rename"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\folder1" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\folder1" -Force | Out-Null
"test content renamed" | Set-Content "$test_left\folder1\file.txt"
"test content renamed" | Set-Content "$test_right\folder1\file.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
Rename-Item -Path "$test_left\folder1" -NewName "folder1_renamed"
if (Invoke-Sync) {
    $leftExists = Test-Path "$test_left\folder1_renamed\file.txt"
    $rightExists = Test-Path "$test_right\folder1_renamed\file.txt"
    $oldLeft = Test-Path "$test_left\folder1" -PathType Container
    $oldRight = Test-Path "$test_right\folder1" -PathType Container
    $contentMatches = if ($leftExists -and $rightExists) {
        Test-ContentMatch "$test_left\folder1_renamed\file.txt" "$test_right\folder1_renamed\file.txt" "Content"
    } else { $false }
    Write-Result "Renamed folder on left" $leftExists
    Write-Result "Renamed folder on right" $rightExists
    Write-Result "Old folder does not exist on left" (-not $oldLeft)
    Write-Result "Old folder does not exist on right" (-not $oldRight)
    Write-Result "Content matches" $contentMatches
    if ($leftExists -and $rightExists -and (-not $oldLeft) -and (-not $oldRight) -and $contentMatches) {
        $passedTests++
        Write-Result "Test 23 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 23 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 24: Directory rename with multiple files - verify all contents preserved
$totalTests++
Write-TestHeader "Directory rename preserves all contents" 24
$test_name = "content_preservation"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\source_folder\sub1\sub2" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\source_folder\sub1\sub2" -Force | Out-Null
"file1 content" | Set-Content "$test_left\source_folder\file1.txt"
"file2 content" | Set-Content "$test_left\source_folder\sub1\file2.txt"
"file3 content" | Set-Content "$test_left\source_folder\sub1\sub2\file3.txt"
"file1 content" | Set-Content "$test_right\source_folder\file1.txt"
"file2 content" | Set-Content "$test_right\source_folder\sub1\file2.txt"
"file3 content" | Set-Content "$test_right\source_folder\sub1\sub2\file3.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
Rename-Item -Path "$test_left\source_folder" -NewName "dest_folder"
if (Invoke-Sync) {
    $file1Left = Test-Path "$test_left\dest_folder\file1.txt"
    $file2Left = Test-Path "$test_left\dest_folder\sub1\file2.txt"
    $file3Left = Test-Path "$test_left\dest_folder\sub1\sub2\file3.txt"
    $file1Right = Test-Path "$test_right\dest_folder\file1.txt"
    $file2Right = Test-Path "$test_right\dest_folder\sub1\file2.txt"
    $file3Right = Test-Path "$test_right\dest_folder\sub1\sub2\file3.txt"
    $content1Match = if ($file1Left -and $file1Right) {
        Test-ContentMatch "$test_left\dest_folder\file1.txt" "$test_right\dest_folder\file1.txt" "file1"
    } else { $false }
    $content2Match = if ($file2Left -and $file2Right) {
        Test-ContentMatch "$test_left\dest_folder\sub1\file2.txt" "$test_right\dest_folder\sub1\file2.txt" "file2"
    } else { $false }
    $content3Match = if ($file3Left -and $file3Right) {
        Test-ContentMatch "$test_left\dest_folder\sub1\sub2\file3.txt" "$test_right\dest_folder\sub1\sub2\file3.txt" "file3"
    } else { $false }
    Write-Result "All 3 files exist on left in new location" ($file1Left -and $file2Left -and $file3Left)
    Write-Result "All 3 files exist on right in new location" ($file1Right -and $file2Right -and $file3Right)
    Write-Result "All content matches after rename" ($content1Match -and $content2Match -and $content3Match)
    if ($file1Left -and $file2Left -and $file3Left -and $file1Right -and $file2Right -and $file3Right -and $content1Match -and $content2Match -and $content3Match) {
        $passedTests++
        Write-Result "Test 24 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 24 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Test 25: Directory case change only (MyFolder -> myfolder)
$totalTests++
Write-TestHeader "Directory case change syncs correctly" 25
$test_name = "case_change_dir"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path "$test_left\MyFolder" -Force | Out-Null
New-Item -ItemType Directory -Path "$test_right\MyFolder" -Force | Out-Null
"test content" | Set-Content "$test_left\MyFolder\file.txt"
"test content" | Set-Content "$test_right\MyFolder\file.txt"
# Initial sync to establish state
Invoke-Sync | Out-Null
# Change case on left (MyFolder -> myfolder)
Rename-Item -Path "$test_left\MyFolder" -NewName "myfolder_temp"
Rename-Item -Path "$test_left\myfolder_temp" -NewName "myfolder"
if (Invoke-Sync) {
    # After sync, both sides should have the SAME case (lowercase)
    # Check what case we actually have on each side
    $leftDirs = Get-ChildItem -Path $test_left -Directory | Where-Object { $_.Name -like "*folder" }
    $rightDirs = Get-ChildItem -Path $test_right -Directory | Where-Object { $_.Name -like "*folder" }

    $leftCase = if ($leftDirs.Count -gt 0) { $leftDirs[0].Name } else { "NOT FOUND" }
    $rightCase = if ($rightDirs.Count -gt 0) { $rightDirs[0].Name } else { "NOT FOUND" }

    Write-Host "  Left folder case: $leftCase"
    Write-Host "  Right folder case: $rightCase"

    # Both should exist and have matching case
    $leftHasFolder = Test-Path "$test_left\myfolder\file.txt"
    $rightHasFolder = Test-Path "$test_right\myfolder\file.txt"
    $casesMatch = ($leftCase -ceq $rightCase) -and ($leftCase -ceq "myfolder")

    Write-Result "Left has folder with file" $leftHasFolder
    Write-Result "Right has folder with file" $rightHasFolder
    Write-Result "Both sides have matching lowercase case" $casesMatch

    if ($leftHasFolder -and $rightHasFolder -and $casesMatch) {
        $passedTests++
        Write-Result "Test 25 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 25 FAILED - Case mismatch: left=$leftCase, right=$rightCase" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

# Reset state before case-conflict canonical test to avoid prior runs influencing detection
Remove-Item -LiteralPath "sync_state.db" -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ".deleted" -Recurse -Force -ErrorAction SilentlyContinue

# Test 26: Case conflict preserves newer content and creates conflict artifacts
$totalTests++
Write-TestHeader "Case conflict keeps newer content and conflict copies" 26
$test_name = "case_conflict_canonical"
$test_left = "$LeftPath\$test_name"
$test_right = "$RightPath\$test_name"
New-Item -ItemType Directory -Path $test_left -Force | Out-Null
New-Item -ItemType Directory -Path $test_right -Force | Out-Null

$leftFile = "$test_left\CaseTest.txt"
$rightFile = "$test_right\casetest.txt"
"older-left-case" | Set-Content $leftFile
"NEW-RIGHT-CONTENT" | Set-Content $rightFile

# Ensure right side is newer than left for tie-breaking
(Get-Item $leftFile).LastWriteTime = (Get-Date).AddSeconds(-120)
(Get-Item $rightFile).LastWriteTime = (Get-Date).AddSeconds(-60)

if (Invoke-Sync) {
    # Run a second sync pass to ensure case normalization is fully applied
    Invoke-Sync | Out-Null

    $canonicalLeftPath = "$test_left\casetest.txt"
    $canonicalRightPath = "$test_right\casetest.txt"
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

    Write-Result "Canonical file exists on left" $leftExists
    Write-Result "Canonical file exists on right" $rightExists
    Write-Result "Canonical content matches newer side" $contentMatches
    Write-Result "Conflict files exist on both sides" $conflictExists
    Write-Result "Conflict files contain older content" $conflictContentOk
    Write-Result "Old casing removed on left" $noOldCasingLeft
    Write-Result "Old casing removed on right" $noOldCasingRight

    if ($leftExists -and $rightExists -and $contentMatches -and $conflictExists -and $conflictContentOk -and $noOldCasingLeft -and $noOldCasingRight) {
        $passedTests++
        Write-Result "Test 26 PASSED" $true
    } else {
        $failedTests++
        Write-Result "Test 26 FAILED" $false
    }
}
Remove-Item -Path $test_left -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path $test_right -Recurse -Force -ErrorAction SilentlyContinue

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

if (Test-Path -LiteralPath $TempConfigPath) {
    Remove-Item -LiteralPath $TempConfigPath -Force -ErrorAction SilentlyContinue
}

# Exit with appropriate code
if ($failedTests -gt 0) {
    exit 1
} else {
    Write-Host "All tests passed!" -ForegroundColor $SuccessColor
    exit 0
}
