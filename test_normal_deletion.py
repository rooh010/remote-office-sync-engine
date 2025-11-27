"""Test for normal file deletion syncing."""

import tempfile
from pathlib import Path
from remote_office_sync.scanner import Scanner
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncEngine, SyncAction
from remote_office_sync.config_loader import Config


def test_normal_deletion():
    """Test that normal deletions work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        left_dir = tmppath / "left"
        right_dir = tmppath / "right"
        left_dir.mkdir()
        right_dir.mkdir()

        db_path = tmppath / "test.db"

        config = Config({
            "left_root": str(left_dir),
            "right_root": str(right_dir),
            "soft_delete": {"enabled": False}
        })

        # Step 1: Create normal.txt on both sides
        (left_dir / "normal.txt").write_text("content")
        (right_dir / "normal.txt").write_text("content")

        # First sync - should recognize file exists on both sides
        scanner = Scanner()
        left_scan = scanner.scan_directory(str(left_dir))
        right_scan = scanner.scan_directory(str(right_dir))
        current_state = scanner.merge_scans(left_scan, right_scan)

        state_db = StateDB(str(db_path))
        previous_state = state_db.load_state()

        engine = SyncEngine(config, previous_state, current_state)
        jobs = engine.generate_sync_jobs()

        print("=== First Sync Jobs (should be empty or NOOP) ===")
        for job in jobs:
            print(f"{job.action.value}: {job.file_path} - {job.details}")

        # Save state
        state_db.save_state(current_state)

        print("\n=== State after first sync ===")
        for path, meta in current_state.items():
            print(f"{path}: left={meta.exists_left}, right={meta.exists_right}")

        # Step 2: Delete normal.txt from left
        (left_dir / "normal.txt").unlink()

        print("\n=== After deleting normal.txt from left ===")
        print(f"Left files: {[f.name for f in left_dir.iterdir()]}")
        print(f"Right files: {[f.name for f in right_dir.iterdir()]}")

        # Second sync - should delete from right
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

        # Check if deletion is properly synced
        delete_jobs = [j for j in jobs if j.action == SyncAction.DELETE_RIGHT and j.file_path == "normal.txt"]

        if delete_jobs:
            print("\n✓ SUCCESS: Found DELETE_RIGHT job for normal.txt")
        else:
            print("\n✗ FAILURE: No DELETE_RIGHT job for normal.txt found!")
            print("BUG CONFIRMED: Normal deletions are not synced")


if __name__ == "__main__":
    test_normal_deletion()
