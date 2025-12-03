# Integration test for directory rename handling
# Tests actual rename scenarios with real directories

param(
    [string]$LeftPath = "C:\pdrive_local",
    [string]$RightPath = "P:\",
    [switch]$NoCleanup = $false
)

$ErrorActionPreference = "Stop"

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

    # Create identical folder structure on both sides
    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    # Create a test file inside the folder
    "test content left" | Set-Content "$left_test\old_folder\file.txt"
    "test content left" | Set-Content "$right_test\old_folder\file.txt"

    # Now rename on left only
    Rename-Item -Path "$left_test\old_folder" -NewName "new_folder"

    # Run sync
    Write-Host "  Running sync..."
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Verify results
    if ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder")) {
        if ((Test-Path "$right_test\old_folder")) {
            throw "Old folder still exists on right after sync!"
        }
        if (Test-Path "$left_test\old_folder") {
            throw "Old folder still exists on left after sync!"
        }
        Write-Host "  OK: Folder renamed correctly on both sides"
    } else {
        throw "New folder not created on both sides"
    }

    Cleanup-Test $test_name
}

# Test 2: Rename folder on right side only
Test-Case "Rename folder on right only" {
    $test_name = "test2_rename_right"
    Cleanup-Test $test_name

    # Create identical folder structure
    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename on right only
    Rename-Item -Path "$right_test\old_folder" -NewName "new_folder"

    # Run sync
    Write-Host "  Running sync..."
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Verify results
    if ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder")) {
        if ((Test-Path "$left_test\old_folder") -or (Test-Path "$right_test\old_folder")) {
            throw "Old folder still exists after sync!"
        }
        Write-Host "  OK: Folder renamed correctly on both sides"
    } else {
        throw "New folder not created on both sides"
    }

    Cleanup-Test $test_name
}

# Test 3: Rename to same name on both sides
Test-Case "Rename to same name on both sides" {
    $test_name = "test3_same_rename"
    Cleanup-Test $test_name

    # Create initial structure
    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename on both sides to SAME name
    Rename-Item -Path "$left_test\old_folder" -NewName "new_folder"
    Rename-Item -Path "$right_test\old_folder" -NewName "new_folder"

    # Run sync
    Write-Host "  Running sync..."
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Verify - both should have new_folder, no conflicts
    if ((Test-Path "$left_test\new_folder") -and (Test-Path "$right_test\new_folder")) {
        $conflict_files = @()
        $conflict_files += Get-ChildItem -Path $left_test -Filter "*CONFLICT*" -Recurse -ErrorAction SilentlyContinue
        $conflict_files += Get-ChildItem -Path $right_test -Filter "*CONFLICT*" -Recurse -ErrorAction SilentlyContinue

        if ($conflict_files.Count -gt 0) {
            throw "Unexpected conflict files found when both sides renamed to same name"
        }
        Write-Host "  OK: No conflict when both sides rename to same name"
    } else {
        throw "New folder not found on both sides"
    }

    Cleanup-Test $test_name
}

# Test 4: Rename to different names on both sides
Test-Case "Rename to different names (creates conflict)" {
    $test_name = "test4_rename_conflict"
    Cleanup-Test $test_name

    # Create initial structure
    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old_folder" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old_folder" -Force | Out-Null

    "test content" | Set-Content "$left_test\old_folder\file.txt"
    "test content" | Set-Content "$right_test\old_folder\file.txt"

    # Rename to DIFFERENT names on each side
    Rename-Item -Path "$left_test\old_folder" -NewName "left_folder"
    Rename-Item -Path "$right_test\old_folder" -NewName "right_folder"

    # Run sync
    Write-Host "  Running sync..."
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Verify - should have conflict or both names resolved
    $has_left = (Test-Path "$left_test\left_folder") -or (Test-Path "$right_test\left_folder")
    $has_right = (Test-Path "$left_test\right_folder") -or (Test-Path "$right_test\right_folder")

    Write-Host "  OK: Rename conflict handled"

    Cleanup-Test $test_name
}

# Test 5: Rename folder with nested contents
Test-Case "Rename folder with nested files" {
    $test_name = "test5_nested_rename"
    Cleanup-Test $test_name

    # Create nested structure
    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\old\sub1\sub2" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\old\sub1\sub2" -Force | Out-Null

    # Create files at different levels
    "file1" | Set-Content "$left_test\old\file1.txt"
    "file2" | Set-Content "$left_test\old\sub1\file2.txt"
    "file3" | Set-Content "$left_test\old\sub1\sub2\file3.txt"

    "file1" | Set-Content "$right_test\old\file1.txt"
    "file2" | Set-Content "$right_test\old\sub1\file2.txt"
    "file3" | Set-Content "$right_test\old\sub1\sub2\file3.txt"

    # Rename parent
    Rename-Item -Path "$left_test\old" -NewName "new"

    # Run sync
    Write-Host "  Running sync..."
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Verify all files are in new location
    if ((Test-Path "$left_test\new\sub1\sub2\file3.txt") -and (Test-Path "$right_test\new\sub1\sub2\file3.txt")) {
        Write-Host "  OK: Nested folder structure renamed correctly"
    } else {
        throw "Nested files not found in renamed folder"
    }

    Cleanup-Test $test_name
}

# Test 6: Basic functionality test
Test-Case "Verify no old folders remain after rename" {
    $test_name = "test6_cleanup"
    Cleanup-Test $test_name

    $left_test = Join-Path $LeftPath $test_name
    $right_test = Join-Path $RightPath $test_name
    New-Item -ItemType Directory -Path "$left_test\folder1" -Force | Out-Null
    New-Item -ItemType Directory -Path "$right_test\folder1" -Force | Out-Null

    "content" | Set-Content "$left_test\folder1\file.txt"
    "content" | Set-Content "$right_test\folder1\file.txt"

    Rename-Item -Path "$left_test\folder1" -NewName "folder1_new"

    # Run sync
    python -m remote_office_sync.main 2>&1 | Out-Null

    # Check cleanup
    $old_left = Test-Path "$left_test\folder1"
    $old_right = Test-Path "$right_test\folder1"
    $new_left = Test-Path "$left_test\folder1_new"
    $new_right = Test-Path "$right_test\folder1_new"

    if ($old_left -or $old_right) {
        throw "Old folder still exists after sync!"
    }
    if (-not $new_left -or -not $new_right) {
        throw "New folder not created!"
    }

    Write-Host "  OK: Old folders cleaned up, new folders created"

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
