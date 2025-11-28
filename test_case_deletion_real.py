"""Test case conflict deletion with real directories.

Scenario:
1. Have test.txt and Test.txt on both sides (from previous case conflict)
2. Delete one variant (e.g., test.txt) from one side (e.g., right)
3. Check if deletion is synced to the other side
"""

import time
from pathlib import Path

from remote_office_sync.config_loader import load_config
from remote_office_sync.scanner import Scanner
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncAction, SyncEngine

# Load actual config
config = load_config("config.yaml")
print(f"Left root: {config.left_root}")
print(f"Right root: {config.right_root}")

# Use subdirectory for testing (to avoid case-insensitive filesystem issues on C:)
test_dir = "case_test"
left_dir = Path(config.left_root) / test_dir
right_dir = Path(config.right_root) / test_dir

# Create test directories
left_dir.mkdir(exist_ok=True)
right_dir.mkdir(exist_ok=True)

# Test files - use relative paths
test_file_lower = f"{test_dir}/test.txt"
test_file_upper = f"{test_dir}/Test.txt"

left_lower = left_dir / "test.txt"
left_upper = left_dir / "Test.txt"
right_lower = right_dir / "test.txt"
right_upper = right_dir / "Test.txt"

# Clean up
for p in [left_lower, left_upper, right_lower, right_upper]:
    if p.exists():
        p.unlink()
        print(f"Cleaned up: {p}")

# Step 1: Create case variant files on both sides
print("\n=== Step 1: Create test.txt and Test.txt on both sides ===")
left_lower.write_text("content lower")
left_upper.write_text("content upper")
right_lower.write_text("content lower")
right_upper.write_text("content upper")
print(f"Created on left: {[f.name for f in left_dir.iterdir()]}")
print(f"Created on right: {[f.name for f in right_dir.iterdir()]}")
time.sleep(0.5)

# Scan and save state
scanner = Scanner()
left_scan = scanner.scan_directory(config.left_root)
right_scan = scanner.scan_directory(config.right_root)
current_state = scanner.merge_scans(left_scan, right_scan)

db_path = "sync_state.db"
state_db = StateDB(db_path)
state_db.save_state(current_state)

print("\n=== State after creating both files ===")
for path, meta in current_state.items():
    if "case_test" in path and "test.txt" in path.lower():
        print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

# Step 2: Delete test.txt (lowercase) from right
print("\n=== Step 2: Delete test.txt from right ===")
if right_lower.exists():
    right_lower.unlink()
    print(f"Deleted: {right_lower}")
else:
    print(f"Warning: {right_lower} doesn't exist - might be case-insensitive filesystem")

print(f"Files on left: {[f.name for f in left_dir.iterdir() if f.is_file()]}")
print(f"Files on right: {[f.name for f in right_dir.iterdir() if f.is_file()]}")
time.sleep(0.5)

# Scan again
left_scan = scanner.scan_directory(config.left_root)
right_scan = scanner.scan_directory(config.right_root)
current_state = scanner.merge_scans(left_scan, right_scan)

print("\n=== Current state after deletion ===")
for path, meta in current_state.items():
    if "case_test" in path and "test.txt" in path.lower():
        print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

previous_state = state_db.load_state()
print("\n=== Previous state from DB ===")
for path, meta in previous_state.items():
    if "case_test" in path and "test.txt" in path.lower():
        print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

# Generate jobs
engine = SyncEngine(config, previous_state, current_state)
jobs = engine.generate_sync_jobs()

print(f"\n=== Jobs after deletion: {len(jobs)} ===")
for job in jobs:
    if "case_test" in job.file_path:
        print(f"  {job.action.value}: {job.file_path} - {job.details}")

# Check for deletion job for test.txt
delete_jobs = [
    j
    for j in jobs
    if "test.txt" in j.file_path.lower()
    and (
        j.action == SyncAction.DELETE_LEFT
        or j.action == SyncAction.SOFT_DELETE_LEFT
        or j.action == SyncAction.DELETE_RIGHT
        or j.action == SyncAction.SOFT_DELETE_RIGHT
    )
]

if delete_jobs:
    print("\n[OK] Case-specific deletion would be synced")
    for job in delete_jobs:
        print(f"  {job.action.value}: {job.file_path}")
else:
    print("\n[ERROR] No deletion job found for case-specific deletion - BUG CONFIRMED")

# Clean up
time.sleep(0.5)
for p in [left_lower, left_upper, right_lower, right_upper]:
    if p.exists():
        p.unlink()
