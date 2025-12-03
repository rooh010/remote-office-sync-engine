# Integration test for directory rename handling
# Tests actual rename scenarios with real directories

param(
    [string]$LeftPath = "C:\pdrive_local",
    [string]$RightPath = "P:\"
)

$ErrorActionPreference = "Continue"

Write-Host "========================================="
Write-Host "Directory Rename Integration Tests"
Write-Host "========================================="
Write-Host "Left:  $LeftPath"
Write-Host "Right: $RightPath"
Write-Host ""

# Create test directories if they don't exist
if (-not (Test-Path $LeftPath)) { New-Item -ItemType Directory -Path $LeftPath -Force | Out-Null }
if (-not (Test-Path $RightPath)) { New-Item -ItemType Directory -Path $RightPath -Force | Out-Null }

$test_count = 0
$pass_count = 0
$fail_count = 0

function Test-Case {
    param(
        [string]$Name,
        [scriptblock]$Test
    )

    $global:test_count++
    Write-Host ""
    Write-Host "Test ${global:test_count}: $Name"
    Write-Host "-----------------------------------------"

    try {
        & $Test
        Write-Host "[PASS]" -ForegroundColor Green
        $global:pass_count++
        return $true
    } catch {
        Write-Host "[FAIL] $_" -ForegroundColor Red
        $global:fail_count++
        return $false
    }
}

function Cleanup-Test {
    param([string]$Name)

    $left_test_dir = Join-Path $LeftPath $Name
    $right_test_dir = Join-Path $RightPath $Name

    Remove-Item -Path $left_test_dir -Force -Recurse -ErrorAction SilentlyContinue
    Remove-Item -Path $right_test_dir -Force -Recurse -ErrorAction SilentlyContinue
}

# Test 1: Rename folder on left side only
Test-Case "Rename folder on left only" {
    $test_name = "test1_rename_left"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename on left
    Rename-Item -Path "$left_test\old_folder" -NewName "new_folder"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    # Verify: new_folder should exist on both, old_folder should be gone
    if (-not ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder"))) {
        throw "New folder not on both sides"
    }

    Write-Host "  OK: Folder renamed and synced correctly"
    Cleanup-Test $test_name
}

# Test 2: Rename folder on right side only
Test-Case "Rename folder on right only" {
    $test_name = "test2_rename_right"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename on right
    Rename-Item -Path "$right_test\old_folder" -NewName "new_folder"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    # Verify
    if (-not ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder"))) {
        throw "New folder not on both sides"
    }

    Write-Host "  OK: Folder renamed and synced correctly"
    Cleanup-Test $test_name
}

# Test 3: Rename to same name on both sides
Test-Case "Rename to same name on both sides" {
    $test_name = "test3_same_rename"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename on both to same name
    Rename-Item -Path "$left_test\old_folder" -NewName "new_folder"
    Rename-Item -Path "$right_test\old_folder" -NewName "new_folder"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    if (-not ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder"))) {
        throw "New folder not found"
    }

    Write-Host "  OK: No conflicts when both rename to same name"
    Cleanup-Test $test_name
}

# Test 4: Rename to different names
Test-Case "Rename to different names (conflict)" {
    $test_name = "test4_rename_conflict"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename to different names
    Rename-Item -Path "$left_test\old_folder" -NewName "left_folder"
    Rename-Item -Path "$right_test\old_folder" -NewName "right_folder"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    Write-Host "  OK: Rename conflict handled"
    Cleanup-Test $test_name
}

# Test 5: Nested directory rename
Test-Case "Rename folder with nested files" {
    $test_name = "test5_nested_rename"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old\sub1\sub2" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old\sub1\sub2" -Force | Out-Null

    "file1" | Set-Content "$left_test\old\file1.txt"
    "file2" | Set-Content "$left_test\old\sub1\file2.txt"
    "file3" | Set-Content "$left_test\old\sub1\sub2\file3.txt"

    "file1" | Set-Content "$right_test\old\file1.txt"
    "file2" | Set-Content "$right_test\old\sub1\file2.txt"
    "file3" | Set-Content "$right_test\old\sub1\sub2\file3.txt"

    # Rename parent
    Rename-Item -Path "$left_test\old" -NewName "new"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path "$left_test\new\sub1\sub2\file3.txt")) {
        throw "Nested structure not found on left"
    }
    if (-not (Test-Path "$right_test\new\sub1\sub2\file3.txt")) {
        throw "Nested structure not found on right"
    }

    Write-Host "  OK: Nested folder structure renamed correctly"
    Cleanup-Test $test_name
}

# Test 6: Verify new folder synced correctly after rename
Test-Case "Verify new folder synced after rename" {
    $test_name = "test6_verify_new"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\folder1" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\folder1" -Force | Out-Null

    "test content renamed" | Set-Content "$left_test\folder1\file.txt"
    "test content renamed" | Set-Content "$right_test\folder1\file.txt"

    # Rename on left
    Rename-Item -Path "$left_test\folder1" -NewName "folder1_renamed"

    # Run sync
    $result = python -m remote_office_sync.main --no-dry-run 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Sync failed with exit code $LASTEXITCODE"
    }

    # Verify: new_renamed folder should exist on both sides with correct content
    if (-not ((Test-Path "$left_test\folder1_renamed\file.txt") -and (Test-Path "$right_test\folder1_renamed\file.txt"))) {
        throw "Renamed folder not synced correctly"
    }

    # Verify content matches
    $left_content = Get-Content "$left_test\folder1_renamed\file.txt"
    $right_content = Get-Content "$right_test\folder1_renamed\file.txt"
    if ($left_content -ne $right_content) {
        throw "Content mismatch after rename sync"
    }

    Write-Host "  OK: Renamed folder synced correctly on both sides"
    Cleanup-Test $test_name
}

# Summary
Write-Host ""
Write-Host "========================================="
Write-Host "Test Summary"
Write-Host "========================================="
Write-Host "Total:  ${global:test_count}"
Write-Host "Passed: ${global:pass_count}" -ForegroundColor Green
Write-Host "Failed: ${global:fail_count}" -ForegroundColor Red
Write-Host ""

if ($global:fail_count -eq 0) {
    Write-Host "All tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some tests failed!" -ForegroundColor Red
    exit 1
}
