# How the Sync Engine Works

## Overview

The Remote Office Sync Engine uses a **three-way comparison** to detect changes and determine what needs to sync. It compares:

1. **Previous State** (from last sync - stored in `sync_state.db`)
2. **Current Left State** (scanned from left directory)
3. **Current Right State** (scanned from right directory)

## Change Detection

### What We Track for Each File

For every file, we store:
- `relative_path` - Path relative to root (e.g., `documents/report.docx`)
- `exists_left` - Whether file exists on left side
- `exists_right` - Whether file exists on right side
- `mtime_left` - Modification time on left side (Unix timestamp)
- `mtime_right` - Modification time on right side
- `size_left` - File size on left side (bytes)
- `size_right` - File size on right side

### How We Detect Changes

The engine compares modification times (`mtime`) to detect changes:

```python
# Example: File modified on left
if prev_metadata.mtime_left != curr_metadata.mtime_left:
    # File was modified on left side
    # → Copy from left to right
```

## Sync Decision Logic

### 1. New Files

**Scenario**: File exists now but didn't exist in previous sync

```
Previous: None
Current:  exists_left=True, exists_right=False
Action:   COPY_LEFT_TO_RIGHT (copy new file to right)
```

**Example**: You create `report.docx` on left side
- Engine sees: No previous state for `report.docx`
- Current: Exists on left only
- **Action**: Copy `report.docx` from left → right

### 2. Modified Files

**Scenario**: File exists on both sides, but mtime changed on one side

```
Previous: mtime_left=100, mtime_right=100
Current:  mtime_left=200, mtime_right=100
Action:   COPY_LEFT_TO_RIGHT (left was modified)
```

**Example**: You edit `report.docx` on left side
- Previous sync: Both sides had mtime=100
- Current scan: Left has mtime=200 (changed), right still 100
- **Action**: Copy updated `report.docx` from left → right

### 3. Deleted Files

**Scenario**: File existed before but is now gone from one side

```
Previous: exists_left=True, exists_right=True
Current:  exists_left=False, exists_right=True (unchanged)
Action:   DELETE_RIGHT or SOFT_DELETE_RIGHT
```

**Example**: You delete `old_report.docx` from left
- Previous: File existed on both sides
- Current: Gone from left, still on right (same mtime)
- **Action**: Delete from right (or move to `.deleted/` if soft delete enabled)

### 4. Conflicts

**Scenario**: File modified on BOTH sides since last sync

```
Previous: mtime_left=100, mtime_right=100
Current:  mtime_left=200, mtime_right=150
Conflict: MODIFY_MODIFY
```

**Example**: You edit `report.docx` on BOTH left and right
- Previous: Both had mtime=100
- Current: Left=200, Right=150 (both changed!)
- **Action**:
  - Determine which is newer (left=200 is newer)
  - Save older version as `report.CONFLICT.20251122_143052.docx`
  - Keep newer version as main file
  - Run second sync to sync conflict file to both sides

## The 13 Sync Rules

### New File Rules
1. **New on left only** → Copy to right
2. **New on right only** → Copy to left

### Modified File Rules
3. **Modified on left only** → Copy to right
4. **Modified on right only** → Copy to left
5. **Modified on both** → Conflict (apply conflict policy)

### Deleted File Rules
6. **Deleted on left, unchanged on right** → Delete right
7. **Deleted on left, changed on right** → Copy right to left (right wins)
8. **Deleted on right, unchanged on left** → Delete left
9. **Deleted on right, changed on left** → Copy left to right (left wins)

### Conflict Rules
10. **Modify-Modify conflict** → Apply `modify_modify` policy (clash/overwrite/notify)
11. **New-New conflict** → Apply `new_new` policy (same filename, different content)
12. **Metadata conflict** → Apply `metadata_conflict` policy (size mismatch)
13. **No changes** → NOOP (do nothing)

## Example Walkthrough

Let's trace a complete sync scenario:

### Initial State (First Sync)
```
Left:  report.docx (mtime=100, size=1024)
Right: (empty)
DB:    (empty)
```

**First Sync**:
1. Scanner finds: `report.docx` exists on left only
2. Previous state: None (first sync)
3. Rule applied: New on left only
4. **Action**: Copy left → right
5. **Result**: Both sides now have `report.docx`
6. Database saved:
   ```
   path: report.docx
   exists_left: 1, exists_right: 1
   mtime_left: 100, mtime_right: 100
   size_left: 1024, size_right: 1024
   ```

### You Edit File on Left
```
Left:  report.docx (mtime=200, size=2048) ← EDITED
Right: report.docx (mtime=100, size=1024)
DB:    mtime_left=100, mtime_right=100
```

**Second Sync**:
1. Scanner finds: `report.docx` exists on both
2. Previous state: mtime_left=100, mtime_right=100
3. Current state: mtime_left=200 (changed!), mtime_right=100 (same)
4. Rule applied: Modified on left only
5. **Action**: Copy left → right
6. **Result**: Right gets updated file
7. Database updated:
   ```
   mtime_left: 200, mtime_right: 200
   size_left: 2048, size_right: 2048
   ```

### Both Sides Edited (Conflict!)
```
Left:  report.docx (mtime=300, size=3000) ← EDITED ON LEFT
Right: report.docx (mtime=250, size=2500) ← EDITED ON RIGHT
DB:    mtime_left=200, mtime_right=200
```

**Third Sync**:
1. Scanner finds: `report.docx` exists on both
2. Previous: mtime_left=200, mtime_right=200
3. Current: mtime_left=300 (changed!), mtime_right=250 (changed!)
4. **Conflict detected**: MODIFY_MODIFY
5. Policy: `clash` (default)
6. **Actions**:
   - Compare mtimes: left=300 > right=250 (left is newer)
   - Create `report.CONFLICT.20251122_143052.docx` from right (older)
   - Copy left → right (newer becomes main)
7. **Second Sync** (automatic):
   - Sync the conflict file to left side
8. **Result**: Both sides have:
   - `report.docx` (newer content from left, mtime=300)
   - `report.CONFLICT.20251122_143052.docx` (older content from right)

## Key Points

1. **Modification time is the signal**: When a file's `mtime` changes, we know it was modified
2. **Three-way comparison**: We need previous state to know WHAT changed WHERE
3. **Authoritative changes win**: If you modify a file that was deleted on the other side, your change wins
4. **Conflicts preserve both versions**: Clash policy saves older version, keeps newer as main
5. **Database is critical**: Without `sync_state.db`, the engine can't detect changes (would treat everything as new)

## Case Sensitivity

All file paths and names are **case-sensitive**:
- `Document.txt` and `document.txt` are treated as DIFFERENT files
- If you rename `File.txt` → `file.txt`, the engine detects:
  - Delete: `File.txt`
  - New: `file.txt`
- Both operations sync to other side

## Why This Works

This approach is called **state-based synchronization**:
- We don't watch files in real-time
- Instead, we compare snapshots before and after
- By comparing to previous state, we can infer what happened:
  - mtime changed → file was modified
  - File appeared → file was created
  - File disappeared → file was deleted
  - Both mtimes changed → conflict

This is robust, simple, and doesn't require constant monitoring or file system events.
