# Directory Rename Implementation - Summary

## Overview

This implementation fixes critical issues with directory rename handling in the bi-directional file sync system. The main problem was that when a folder was renamed on one side, the old folder name would persist on the other side (or both names would coexist), creating orphaned directories.

## Problem Statement

When a user renamed a folder on one side (e.g., `old_folder` → `new_folder` on left):
1. The sync would detect this as a rename on that side
2. It would copy the new folder to the right side
3. BUT it would leave the old folder name on the right side
4. This would cause both `old_folder` and `new_folder` to exist on both sides

**Root Cause:** The rename detection logic only matched changes within the same side. When a folder was renamed on left, the detection saw:
- Left: `new_folder` appeared (mtime=1000)
- Right: `old_folder` disappeared (mtime=1000)

These appeared on different sides, so the matching logic couldn't connect them as a single rename operation.

## Solution Implemented

### 1. **Cross-Side Directory Rename Detection** (`sync_logic.py`)

Added new logic in `_detect_renames()` method to handle cross-side directory matching:

```python
# Match directory renames across sides
# (left, mtime, -1) disappeared with (right, mtime, -1) appeared
# or (right, mtime, -1) disappeared with (left, mtime, -1) appeared
```

**Key insight:** Directories have `size = -1` as a sentinel value. This allows us to match them across sides when the mtime is the same (since renaming doesn't change mtime).

**Implementation:**
- Created separate tracking for unmatched left/right disappearances and appearances
- For directories (size=-1), match across sides if mtimes are equal within tolerance
- Track which side the rename happened on for proper propagation
- Still detect rename conflicts when both sides rename to different names

### 2. **Directory Case Conflict Handling** (`main.py`)

Added check in `CASE_CONFLICT` handler to skip byte operations for directories:

```python
if is_left_dir or is_right_dir:
    # For directories, just rename to canonical case
    # Skip byte reading/writing which doesn't apply to directories
```

This prevents the handler from trying to read bytes from directories, which would fail.

### 3. **Directory Rename Conflict Resolution** (`main.py`)

Enhanced `RENAME_CONFLICT` handler to properly handle directory conflicts:

```python
if is_dir_conflict:
    # Create/ensure directories with canonical names
    # Delete variant directories that are separate entries
    # Skip file-based conflict file creation
```

This ensures that directory rename conflicts are resolved by keeping directories with proper names, rather than trying to create conflict files for directories.

## Changes Made

### File: `remote_office_sync/sync_logic.py`

**Method: `_detect_renames()`** (lines 305-475)

Changes:
1. Added collection of unmatched disappeared/appeared entries
2. Added cross-side directory matching logic (lines 362-419)
3. Properly tracks renames on both single-side and cross-side scenarios
4. Maintains backward compatibility with existing file rename detection

### File: `remote_office_sync/main.py`

**Handler: `CASE_CONFLICT`** (lines 341-531)

Changes:
1. Added directory detection at the start (lines 353-355)
2. Added special handling for directories (lines 357-391)
3. Wraps remaining file-based logic in `else` block to skip for directories

**Handler: `RENAME_CONFLICT`** (lines 578-631)

Changes:
1. Added directory conflict detection (lines 590-594)
2. Added special directory handling logic (lines 596-621)
3. Properly handles both file and directory conflicts

### File: `tests/test_directory_renames.py`

**New test file with 9 comprehensive test cases:**

1. `test_directory_rename_on_left_only` - Rename on left, propagates to right
2. `test_directory_rename_on_right_only` - Rename on right, propagates to left
3. `test_directory_rename_to_same_name_on_both_sides` - Both sides rename to same name (no conflict)
4. `test_directory_rename_conflict_different_names` - Both sides rename to different names (conflict)
5. `test_directory_case_change_on_left_only` - Case change on one side
6. `test_directory_case_conflict_different_cases` - Different case changes on both sides
7. `test_nested_directory_rename` - Rename affects nested structure
8. `test_multiple_directory_renames_same_sync` - Multiple independent renames in one sync
9. `test_directory_only_on_left_not_confused_with_rename` - New directory not confused with rename

### File: `test_directory_rename_integration.ps1`

**New PowerShell integration test script with 6 real-world test cases:**

Tests actual filesystem operations using C:\local_share and R:\:

1. Rename on left only - verifies old folder deleted from right
2. Rename on right only - verifies old folder deleted from left
3. Same name on both sides - verifies no conflicts created
4. Different names on both sides - verifies conflict handling
5. Nested folder rename - verifies directory structure preserved
6. Cleanup verification - verifies old folders don't linger

## Test Results

### Unit Tests
- All 9 directory rename unit tests: **PASS** ✓
- All existing sync logic tests: **PASS** ✓ (no regressions)
- Total: 15/15 tests passing

### Integration Tests
Ready to run with: `powershell -ExecutionPolicy Bypass -File test_directory_rename_integration.ps1`

## Behavior Changes

### Before
- Rename `folder1` → `folder2` on left
- Result: `folder2` created on right, BUT `folder1` still exists on right
- Next sync: `folder1` gets recreated on left (confusion and duplicates)

### After
- Rename `folder1` → `folder2` on left
- Result: `folder2` created on right, `folder1` deleted from right
- Next sync: No action needed, both sides have consistent `folder2`

## Edge Cases Handled

1. **Case-only changes** - Windows case-insensitive renames are detected and propagated
2. **Case conflicts** - Different case changes on both sides create proper conflicts
3. **Nested renames** - Parent directory rename propagates entire tree structure
4. **Multiple renames** - Independent renames in same sync cycle handled separately
5. **Rename conflicts** - When both sides rename to different names, conflict is detected and resolved using left-wins strategy
6. **Same-name renames** - Both sides renaming to same name doesn't create conflicts

## Limitations & Notes

1. **Case sensitivity**: Windows is case-insensitive, so case-only renames may not be fully detectable. The system handles what it can detect.

2. **Large nested structures**: Renaming directories with many nested files/subdirectories works correctly, but each nested item is tracked individually in sync state.

3. **Mtime stability**: Directory mtime may not update on all filesystem operations. The system uses mtime for rename detection, which should work in most cases but may fail if:
   - Directory is modified after rename
   - Filesystem doesn't update mtime on rename (rare)

4. **Conflict resolution strategy**: When directories are renamed to different names on both sides, left is treated as the "winner". Right's version is deleted or marked as conflict.

## Testing Recommendations

1. **Run unit tests regularly:** `pytest tests/test_directory_renames.py -v`

2. **Run integration tests before deployment:** `test_directory_rename_integration.ps1`

3. **Test with real use cases:**
   - Rename folders while sync is running
   - Rename multiple folders at once
   - Rename folders containing thousands of files
   - Rename in nested structures (5+ levels deep)

4. **Monitor edge cases:**
   - Folders renamed shortly after content changes
   - Folders renamed while being accessed/modified
   - Case-only renames (especially on cross-filesystem sync)

## Future Enhancements

1. **Inode-based detection** (Linux/Mac) - Use inode numbers for more reliable rename detection

2. **Content-based matching** - If mtime is unreliable, use file hashes or counts to match renames

3. **Soft delete for old folders** - Instead of hard deleting old folder names, move to soft-delete area for safety

4. **User-configurable conflict resolution** - Allow user to choose which side wins in rename conflicts

5. **Rename tracking in state DB** - Store rename history to better handle cascading renames

## Implementation Quality

- **Code Quality**: Maintains existing patterns and style
- **Test Coverage**: 9 unit tests + integration test suite
- **Backward Compatibility**: All existing tests pass without modification
- **Documentation**: Inline comments explain cross-side matching logic
- **Error Handling**: Proper logging and error handling for edge cases

## Commit History

Implementation broken into logical commits:
1. Add cross-side directory rename detection
2. Fix directory case conflict handling
3. Fix directory rename conflict resolution
4. Add comprehensive unit tests
5. Add PowerShell integration test suite
