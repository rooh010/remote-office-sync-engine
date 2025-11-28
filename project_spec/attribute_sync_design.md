# File Attribute Synchronization Design

## Overview

This document describes the design for synchronizing file attributes (Hidden, Read-only, Archive) between left and right directories in the Remote Office Sync Engine.

## Motivation

Users may set file attributes (e.g., marking files as hidden or read-only) on one side of the sync. These attributes should be synchronized to the other side automatically to maintain consistency.

## Requirements

- Track three Windows file attributes: Hidden (H), Read-only (R), Archive (A)
- Sync attributes bidirectionally between left and right
- Attribute-only changes (without file content changes) should trigger sync
- Preserve attributes when copying files
- Handle attribute conflicts when both sides change attributes
- Automatically migrate existing databases without user intervention

## Architecture

### 1. Metadata Storage

#### FileMetadata Extension
Add two new fields to `FileMetadata` dataclass:
- `attrs_left: int | None` - Attribute bitmask for left side
- `attrs_right: int | None` - Attribute bitmask for right side

**Attribute Bitmask Format:**
- `0x01` (1): Hidden
- `0x02` (2): Read-only
- `0x04` (4): Archive

Using bitmask allows efficient storage and bitwise comparison.

#### Database Schema Changes
Add two columns to the `files` table:
- `attrs_left INTEGER` - Attribute bitmask on left side
- `attrs_right INTEGER` - Attribute bitmask on right side

Default value: `NULL` (no attributes tracked)

### 2. Automatic Schema Migration

Implement a database migration system with version tracking to handle existing databases:

**Schema Version Table:**
```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Migration Strategy:**
- Current version: 1 (initial schema)
- Target version: 2 (add attribute columns)
- Migrations are idempotent - safe to run multiple times
- Run automatically on StateDB initialization
- Existing data is preserved, new columns default to NULL

**Benefits:**
- Existing user databases automatically upgraded
- No manual intervention required
- Future schema changes can use same infrastructure

### 3. File Attribute Reading (Windows)

Use Win32 API via `ctypes` to read file attributes:

**Implementation:**
```python
def get_file_attributes(path: Path) -> int:
    """Read Windows file attributes and convert to bitmask.

    Uses Win32 GetFileAttributesW API.

    Returns:
        Bitmask: 0x01=Hidden, 0x02=ReadOnly, 0x04=Archive
    """
```

**Win32 API Mapping:**
- `FILE_ATTRIBUTE_HIDDEN = 0x2` → Our `0x01`
- `FILE_ATTRIBUTE_READONLY = 0x1` → Our `0x02`
- `FILE_ATTRIBUTE_ARCHIVE = 0x20` → Our `0x04`

**Cross-Platform Behavior:**
- Windows: Read actual attributes using Win32 API
- Non-Windows: Return 0 (no attributes)
- Errors: Return 0 and log warning

### 4. File Attribute Writing (Windows)

Use Win32 API to write file attributes:

**Implementation:**
```python
def set_file_attributes(self, path: Path, attrs: int) -> bool:
    """Set Windows file attributes from bitmask.

    Uses Win32 SetFileAttributesW API.

    Returns:
        True if successful, False otherwise
    """
```

**Conversion:**
- Our `0x01` → `FILE_ATTRIBUTE_HIDDEN = 0x2`
- Our `0x02` → `FILE_ATTRIBUTE_READONLY = 0x1`
- Our `0x04` → `FILE_ATTRIBUTE_ARCHIVE = 0x20`
- Base: `FILE_ATTRIBUTE_NORMAL = 0x80` (required by Win32)

**Error Handling:**
- Log errors at WARNING level
- Return False on failure
- Sync continues even if attribute setting fails

### 5. Scanning Process

Update `Scanner.scan_directory()` to collect attributes:

**Return Type Change:**
- Before: `Dict[str, tuple[float, int]]` (mtime, size)
- After: `Dict[str, tuple[float, int, int]]` (mtime, size, attrs)

**Process:**
1. Iterate through files (existing logic)
2. Get mtime and size (existing logic)
3. Call `get_file_attributes()` for each file
4. Return attributes as third tuple element

**Merge Scans:**
Update `merge_scans()` to:
1. Extract attributes from left scan
2. Extract attributes from right scan
3. Store in `FileMetadata.attrs_left` and `FileMetadata.attrs_right`

### 6. Attribute Change Detection

Add to `SyncAction` enum:
- `SYNC_ATTRS_LEFT_TO_RIGHT`: Sync attributes from left to right
- `SYNC_ATTRS_RIGHT_TO_LEFT`: Sync attributes from right to left

**Detection Logic in `determine_sync_jobs()`:**

```python
# After handling content changes, check for attribute-only changes
if (file exists on both sides AND
    content unchanged AND
    attrs_left != attrs_right):

    # Determine which side changed attributes
    if prev_attrs_left != curr_attrs_left:
        # Left changed attributes -> sync to right
        generate SYNC_ATTRS_LEFT_TO_RIGHT job
    elif prev_attrs_right != curr_attrs_right:
        # Right changed attributes -> sync to left
        generate SYNC_ATTRS_RIGHT_TO_LEFT job
    else:
        # Both have attributes but differ
        # Use newer mtime as tiebreaker
        if mtime_left > mtime_right:
            generate SYNC_ATTRS_LEFT_TO_RIGHT job
        else:
            generate SYNC_ATTRS_RIGHT_TO_LEFT job
```

**Key Points:**
- Only sync attributes if content is unchanged
- Use modification time as tiebreaker when both sides have different attributes
- Prioritize content changes over attribute changes

### 7. Attribute Preservation on Copy

Update `FileOps.copy_file()`:

**New Parameter:**
- `preserve_attrs: bool = True`

**Process:**
1. Copy file content (existing logic)
2. If `preserve_attrs=True`:
   - Get source attributes with `get_file_attributes()`
   - Set destination attributes with `set_file_attributes()`
   - Log if attribute copying fails (but don't fail the file copy)

### 8. Job Execution

Add handlers in `SyncRunner._execute_job()`:

```python
case SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT:
    # Get attributes from left
    attrs = get_file_attributes(left_path)
    # Apply to right
    success = set_file_attributes(right_path, attrs)

case SyncAction.SYNC_ATTRS_RIGHT_TO_LEFT:
    # Get attributes from right
    attrs = get_file_attributes(right_path)
    # Apply to left
    success = set_file_attributes(left_path, attrs)
```

**Logging:**
- Log which attributes changed (Hidden, Read-only, Archive)
- Log success/failure
- Include in sync summary

## Configuration (Optional)

Add to `config.template.yaml`:

```yaml
attribute_sync:
  enabled: true              # Enable/disable attribute sync
  track_hidden: true         # Sync hidden attribute
  track_readonly: true       # Sync read-only attribute
  track_archive: true        # Sync archive attribute
```

This allows users to disable attribute sync or specific attributes if needed.

## Testing Strategy

### Unit Tests (`tests/test_attribute_sync.py`)

1. **`test_get_file_attributes()`**
   - Set various attributes on test file
   - Verify `get_file_attributes()` returns correct bitmask

2. **`test_set_file_attributes()`**
   - Call `set_file_attributes()` with various bitmasks
   - Verify file attributes are set correctly

3. **`test_attribute_only_change_left_to_right()`**
   - Create file with attributes on left
   - Sync
   - Verify job generated: `SYNC_ATTRS_LEFT_TO_RIGHT`
   - Verify attributes copied to right

4. **`test_attribute_only_change_right_to_left()`**
   - Create file with attributes on right
   - Sync
   - Verify job generated: `SYNC_ATTRS_RIGHT_TO_LEFT`
   - Verify attributes copied to left

5. **`test_attribute_preserved_on_copy()`**
   - Create file on left with attributes
   - Run sync (triggers file copy)
   - Verify attributes preserved on right

6. **`test_attribute_conflict_resolution()`**
   - Create file with different attributes on both sides
   - Use mtime to determine which wins
   - Verify correct attributes synced

7. **`test_attributes_with_directories()`**
   - Verify directories don't trigger attribute sync
   - Attributes only tracked for files

### Integration Test (Test 17)

**File:** `run_manual_tests.ps1`

**Scenario: Attribute Synchronization**

1. Create file on left with Hidden attribute
2. Sync, verify file on right is also hidden
3. Remove hidden on left, set read-only on right
4. Sync, verify attributes updated on both sides
5. Create new file on right with read-only + archive
6. Sync, verify file on left has all attributes
7. Verify both files match on both sides

## Edge Cases and Handling

### Non-Windows Platforms
- `get_file_attributes()` returns 0 (no attributes)
- Sync continues normally, just ignores attributes
- No errors or warnings

### Attribute-Only Changes During File Copy
- Copy file content first
- Then copy attributes
- If attribute copy fails, file still exists with default attributes
- Log warning but don't fail the job

### Read-only Files
- Can't modify read-only files
- Solution: Temporarily remove read-only, modify, restore

### Archive Bit Toggling
- Archive bit changes frequently on Windows
- Only sync when attribute actually differs between sides
- Don't sync if both sides have same content and same attributes

## Implementation Phases

### Phase 1: Database Migration (Phase 1 of overall)
- Implement schema versioning
- Add migration infrastructure
- Test with existing database

### Phase 2: Metadata Tracking (Phase 2 of overall)
- Extend FileMetadata
- Update StateDB to track attributes
- Update Scanner to collect attributes

### Phase 3: Sync Logic (Phase 3 of overall)
- Add detection of attribute changes
- Generate appropriate sync jobs

### Phase 4: File Operations (Phase 4 of overall)
- Implement attribute reading/writing
- Integrate with file copy

### Phase 5: Testing (Phase 5 of overall)
- Unit tests
- Integration test
- Documentation

## Success Criteria

- [✓] Attributes tracked in metadata
- [✓] Attributes persisted in database
- [✓] Existing databases auto-migrated
- [✓] Attributes synced bidirectionally
- [✓] Attribute-only changes trigger sync
- [✓] Attributes preserved when copying files
- [✓] All tests pass
- [✓] No manual intervention required
- [✓] Documentation updated

## Future Enhancements

- Support for more file attributes (compressed, encrypted, sparse)
- Attribute sync configuration per-directory
- Archive bit smart handling (don't sync if only difference)
- Extended attributes (xattr) support for future cross-platform expansion
