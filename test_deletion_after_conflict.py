"""Test for deletion handling after case conflicts are created."""

import tempfile
from pathlib import Path

from remote_office_sync.config_loader import Config
from remote_office_sync.scanner import Scanner
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncAction, SyncEngine


def test_deletion_after_case_conflict():
    """Test that deletions work correctly after case conflict files are created."""
    # Create temporary directories for left and right
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        left_dir = tmppath / "left"
        right_dir = tmppath / "right"
        left_dir.mkdir()
        right_dir.mkdir()

        db_path = tmppath / "test.db"

        # Create config
        config = Config(
            {
                "left_root": str(left_dir),
                "right_root": str(right_dir),
                "conflict_policy": {
                    "modify_modify": "clash",
                    "new_new": "clash",
                    "metadata_conflict": "notify_only",
                },
                "soft_delete": {"enabled": False},
            }
        )

        # Step 1: Create test.txt on left, Test.txt on right
        (left_dir / "test.txt").write_text("content from left")
        (right_dir / "Test.txt").write_text("content from right")

        # Run first sync - should create conflict files
        scanner = Scanner()
        left_scan = scanner.scan_directory(str(left_dir))
        right_scan = scanner.scan_directory(str(right_dir))
        current_state = scanner.merge_scans(left_scan, right_scan)

        state_db = StateDB(str(db_path))
        previous_state = state_db.load_state()

        engine = SyncEngine(config, previous_state, current_state)
        jobs = engine.generate_sync_jobs()

        print("=== First Sync Jobs ===")
        for job in jobs:
            print(f"{job.action.value}: {job.file_path}")

        # Simulate conflict resolution - both files end up on both sides
        (left_dir / "test.txt").write_text("content from left")
        (left_dir / "Test.txt").write_text("content from right")
        (right_dir / "test.txt").write_text("content from left")
        (right_dir / "Test.txt").write_text("content from right")

        # Save state after sync
        left_scan = scanner.scan_directory(str(left_dir))
        right_scan = scanner.scan_directory(str(right_dir))
        synced_state = scanner.merge_scans(left_scan, right_scan)
        state_db.save_state(synced_state)

        print("\n=== State after first sync ===")
        for path, meta in synced_state.items():
            print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

        # Step 2: Delete test.txt from right (but leave it on left)
        (right_dir / "test.txt").unlink()

        print("\n=== After deleting test.txt from right ===")
        print(f"Left files: {[f.name for f in left_dir.iterdir()]}")
        print(f"Right files: {[f.name for f in right_dir.iterdir()]}")

        # Run second sync - should delete test.txt from left to keep in sync
        left_scan = scanner.scan_directory(str(left_dir))
        right_scan = scanner.scan_directory(str(right_dir))
        current_state = scanner.merge_scans(left_scan, right_scan)

        print("\n=== Current state after deletion ===")
        for path, meta in current_state.items():
            print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

        previous_state = state_db.load_state()
        print("\n=== Previous state from DB ===")
        for path, meta in previous_state.items():
            print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

        engine = SyncEngine(config, previous_state, current_state)
        jobs = engine.generate_sync_jobs()

        print("\n=== Second Sync Jobs ===")
        for job in jobs:
            print(f"{job.action.value}: {job.file_path} - {job.details}")

        # Debug: Check what the code sees
        print("\n=== Debug: Checking file existence ===")
        for path in ["test.txt", "Test.txt"]:
            left_p = left_dir / path
            right_p = right_dir / path
            print(f"{path}:")
            print(f"  Left exists: {left_p.exists()}, Right exists: {right_p.exists()}")
            print(f"  In current_state: {path in current_state}")
            print(f"  In previous_state: {path in previous_state}")

        # Check if deletion is properly synced
        delete_jobs = [
            j for j in jobs if j.action == SyncAction.DELETE_LEFT and j.file_path == "test.txt"
        ]

        if delete_jobs:
            print("\n✓ SUCCESS: Found DELETE_LEFT job for test.txt")
        else:
            print("\n✗ FAILURE: No DELETE_LEFT job for test.txt found!")
            print("BUG CONFIRMED: Deletions after case conflicts are not synced properly")


if __name__ == "__main__":
    test_deletion_after_case_conflict()
