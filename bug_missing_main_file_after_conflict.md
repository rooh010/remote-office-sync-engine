# Bug: Main File Missing After Conflict Resolution

## Status
**CRITICAL** - Data loss issue

## Date Reported
2025-11-28

## Summary
After conflict resolution (case conflicts or modify-modify conflicts), only the `.CONFLICT` file remains and the main file is deleted. This is the opposite of expected behavior and causes data loss.

## Expected Behavior
When a conflict occurs:
- **Main file** (without .CONFLICT extension) = NEWEST version (by modification timestamp)
- **.CONFLICT file** = OLDEST version (preserved for reference)
- **Both files** should exist on **both sides** (left and right)

Example:
- `myfile.txt` - contains the newest content
- `myfile.CONFLICT.username.timestamp.txt` - contains the older content

## Actual Behavior
After conflict resolution:
- **Main file is DELETED** or not preserved
- Only the `.CONFLICT` file remains
- User loses access to the newer version

## Evidence

### Case 1: casetest.txt
```bash
# Search results:
C:/pdrive_local/casetest.CONFLICT.Andy.20251128_083936.txt  # EXISTS
p:/casetest.CONFLICT.Andy.20251128_083936.txt             # EXISTS

# But main file is missing:
# casetest.txt - MISSING on both sides
```

Content of conflict file:
```
Testing case changes
```

### Verification
```bash
$ find "C:/pdrive_local/" -name "*casetest*" -o -name "*CaseTest*"
C:/pdrive_local/casetest.CONFLICT.Andy.20251128_083936.txt

$ find "p:/" -name "*casetest*" -o -name "*CaseTest*"
p:/casetest.CONFLICT.Andy.20251128_083936.txt
```

No main file found in any case variation.

## Impact
- **CRITICAL**: Users lose the newer version of their files
- Only the older version is preserved (as .CONFLICT)
- Defeats the purpose of conflict resolution
- Can cause significant data loss

## Affected Scenarios
Potentially affects:
1. **CASE_CONFLICT** - Case conflicts (different casing on each side)
2. **CLASH_CREATE** - Modify-modify conflicts (different content on each side)
3. **NEW_NEW** conflicts - Same filename created on both sides with different content

## Root Cause (Hypothesis)
Looking at the conflict handlers in `remote_office_sync/main.py`:

### CLASH_CREATE Handler (lines 280-333)
```python
# When left_mtime > right_mtime (left is newer):
conflict_file_right = self.file_ops.create_clash_file(
    str(right_path), username=self.username
)  # Creates conflict from right (older) ✓
self.file_ops.copy_file(str(left_path), str(right_path))  # Should copy newer to right
# Copy conflict file to left
conflict_file_left = str(Path(self.config.left_root) / Path(conflict_file_right).name)
self.file_ops.copy_file(conflict_file_right, conflict_file_left)
```

**Potential issues:**
1. `create_clash_file()` creates a copy but original file remains
2. But somewhere the main file is being deleted
3. Possibly during cleanup or in a second sync cycle?
4. Or the state database causes it to be deleted on the next sync?

### CASE_CONFLICT Handler (lines 334+)
Similar logic - creates conflict file from older version, should preserve newer version.

## Reproduction Steps
1. Create a file with different content on both sides (or different case)
2. Run sync
3. Observe: Only .CONFLICT file exists, main file is gone

## Files Involved
- `remote_office_sync/main.py` - Lines 280-333 (CLASH_CREATE), Lines 334+ (CASE_CONFLICT)
- `remote_office_sync/file_ops.py` - Line 145+ (`create_clash_file()`)
- `remote_office_sync/sync_logic.py` - Conflict detection logic

## Next Steps
1. **Debug logging**: Add extensive logging around conflict file creation
2. **State tracking**: Check if state database is causing deletion on subsequent syncs
3. **Test isolation**: Create unit test that reproduces this issue
4. **Fix verification**: After fix, verify with manual test that both files exist
5. **Content verification**: Ensure main file has newest content, conflict has oldest

## Workaround
None - users must restore from backup or .CONFLICT file

## Related Documentation
See `.claude/claude.md` section "Conflict Resolution Behavior (CRITICAL)" for expected behavior.
