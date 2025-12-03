# Case Conflict Regression (Test 26)

## Summary
Manual Test 26 ("Case conflict keeps newer content and conflict copies") currently fails on Windows when syncing `C:\pdrive_local` ⇄ `p:\`. The unit test for case conflicts on Linux passes when the handler is patched, but our runtime behavior diverges on Windows.

## Expected Behavior (Test 26)
- Same file, different casing: `CaseTest.txt` (left, older) vs `casetest.txt` (right, newer).
- After sync:
  - Canonical `casetest.txt` on both sides with newer content (`NEW-RIGHT-CONTENT`).
  - Conflict copies on both sides named `CaseTest.CONFLICT.<user>.<timestamp>.txt` containing the older content (`older-left-case`).
  - No lingering `CaseTest.txt`; only canonical plus conflict copies.

## Current Behavior
- `casetest.txt` exists on both sides, but content is not the newer value.
- Conflict files exist but contain the wrong content.
- Old casing (`CaseTest.txt`) remains present.
- Manual suite result: 25/26 pass; Test 26 fails. (Test 19 warning resolved after reverting recent `main.py` changes.)

## Context / Timeline
- Manual suite originally passed 25/25 (before adding Test 26).
- Added Test 26 and case-conflict fixes in `remote_office_sync/main.py`; unit test (`test_case_conflict_keeps_newer_casing_and_conflict_artifacts`) was made to pass on Linux.
- Those fixes introduced a warning in Test 19 (rename on right). User requested reverting `main.py` to prior state; warning cleared, but Test 26 still fails.
- Current `main.py` is the pre-fix version; unit case-conflict test would fail on CI until a stable fix is reintroduced.

## Hypothesis
- Case normalization on Windows (case-insensitive FS) plus copy/rename ordering is leaving the older casing and/or overwriting newer content when forcing canonical casing. Conflict files might be created from incorrect snapshots.

## Next Steps
- Reapply a safer case-conflict handler that:
  - Copies newer bytes to canonical paths on both sides before removing old casing.
  - Writes conflict files from the older bytes.
  - Removes lingering old-casing entries only when they differ from canonical and not samefile().
- Verify on both Windows manual suite and Linux unit test.
