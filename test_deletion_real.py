"""Test deletion behavior with real directories."""

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

# Test file
test_file = "deletion_test.txt"
left_path = Path(config.left_root) / test_file
right_path = Path(config.right_root) / test_file

# Clean up if exists
for p in [left_path, right_path]:
    if p.exists():
        p.unlink()
        print(f"Cleaned up: {p}")

# Step 1: Create test file on left
print("\n=== Step 1: Create test file on left ===")
left_path.write_text("test content")
print(f"Created: {left_path}")
time.sleep(0.5)

# Scan
scanner = Scanner()
left_scan = scanner.scan_directory(config.left_root)
right_scan = scanner.scan_directory(config.right_root)
current_state = scanner.merge_scans(left_scan, right_scan)

# Load previous state
db_path = "sync_state.db"
state_db = StateDB(db_path)
previous_state = state_db.load_state()

# Generate jobs
engine = SyncEngine(config, previous_state, current_state)
jobs = engine.generate_sync_jobs()

print(f"\nJobs generated: {len(jobs)}")
for job in jobs:
    if test_file in job.file_path:
        print(f"  {job.action.value}: {job.file_path} - {job.details}")

# Save state (simulating successful sync)
state_db.save_state(current_state)

# Simulate the copy (manually copy the file)
if not right_path.exists():
    right_path.write_text("test content")
    print(f"\nSimulated sync: Created {right_path}")

time.sleep(0.5)

# Update state after manual sync
left_scan = scanner.scan_directory(config.left_root)
right_scan = scanner.scan_directory(config.right_root)
current_state = scanner.merge_scans(left_scan, right_scan)
state_db.save_state(current_state)

print("\n=== State after file exists on both sides ===")
if test_file in current_state:
    meta = current_state[test_file]
    print(f"{test_file}: left={meta.exists_left}, right={meta.exists_right}")

# Step 2: Delete from left
print("\n=== Step 2: Delete test file from left ===")
left_path.unlink()
print(f"Deleted: {left_path}")
time.sleep(0.5)

# Scan again
left_scan = scanner.scan_directory(config.left_root)
right_scan = scanner.scan_directory(config.right_root)
current_state = scanner.merge_scans(left_scan, right_scan)

print("\n=== Current state after deletion ===")
for path, meta in current_state.items():
    if test_file in path:
        print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

previous_state = state_db.load_state()
print("\n=== Previous state from DB ===")
for path, meta in previous_state.items():
    if test_file in path:
        print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

# Generate jobs for deletion
engine = SyncEngine(config, previous_state, current_state)
jobs = engine.generate_sync_jobs()

print(f"\n=== Jobs after deletion: {len(jobs)} ===")
for job in jobs:
    if test_file in job.file_path:
        print(f"  {job.action.value}: {job.file_path} - {job.details}")

# Check for deletion job
delete_jobs = [
    j
    for j in jobs
    if test_file in j.file_path
    and (j.action == SyncAction.DELETE_RIGHT or j.action == SyncAction.SOFT_DELETE_RIGHT)
]

if delete_jobs:
    print("\n[OK] Deletion would be synced properly")
else:
    print("\n[ERROR] No deletion job found - BUG CONFIRMED")
    print("\nAll jobs generated:")
    for job in jobs:
        print(f"  {job.action.value}: {job.file_path} - {job.details}")

# Clean up
for p in [left_path, right_path]:
    if p.exists():
        p.unlink()
