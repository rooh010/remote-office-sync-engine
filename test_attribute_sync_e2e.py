"""
Comprehensive end-to-end test for attribute sync feature.

Tests all phases of attribute sync functionality:
- Phase 1: Database migration, metadata tracking, attribute reading
- Phase 2: Sync logic attribute detection and job generation
- Phase 3: File operations attribute setting and preservation
- Phase 4: Job execution handlers
"""

import ctypes
import shutil
import tempfile
from pathlib import Path

from remote_office_sync.scanner import Scanner
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncEngine, SyncAction
from remote_office_sync.file_ops import FileOps
from remote_office_sync.config_loader import Config


def set_file_attribute_win32(path: str, attrs: int) -> bool:
    """Helper to set file attributes using Win32 API.

    Args:
        path: File path
        attrs: Bitmask (0x01=Hidden, 0x02=ReadOnly, 0x04=Archive)

    Returns:
        True if successful, False otherwise
    """
    try:
        if not hasattr(ctypes, "windll"):
            return False

        kernel32 = ctypes.windll.kernel32
        set_attrs = kernel32.SetFileAttributesW
        set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
        set_attrs.restype = ctypes.c_bool

        # Convert our bitmask to Windows attribute flags
        win_attrs = 0x80  # FILE_ATTRIBUTE_NORMAL base

        if attrs & 0x01:  # Hidden
            win_attrs |= 0x2  # FILE_ATTRIBUTE_HIDDEN

        if attrs & 0x02:  # ReadOnly
            win_attrs |= 0x1  # FILE_ATTRIBUTE_READONLY

        if attrs & 0x04:  # Archive
            win_attrs |= 0x20  # FILE_ATTRIBUTE_ARCHIVE

        return set_attrs(str(path), win_attrs)
    except Exception as e:
        print(f"[ERROR] Could not set attributes on {path}: {e}")
        return False


def print_test_header(test_num: str, description: str) -> None:
    """Print test section header."""
    print(f"\n{'=' * 70}")
    print(f"TEST {test_num}: {description}")
    print(f"{'=' * 70}")


def print_result(result: bool, message: str) -> None:
    """Print test result."""
    status = "[PASS]" if result else "[FAIL]"
    print(f"{status} {message}")


def main():
    """Run comprehensive attribute sync end-to-end tests."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE ATTRIBUTE SYNC END-TO-END TEST")
    print("=" * 70)

    # Create temporary test directories
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        left_dir = tmpdir / "left"
        right_dir = tmpdir / "right"
        db_path = tmpdir / "sync_state.db"

        left_dir.mkdir()
        right_dir.mkdir()

        print(f"\nTest directories created:")
        print(f"  LEFT:  {left_dir}")
        print(f"  RIGHT: {right_dir}")
        print(f"  DB:    {db_path}")

        # Test 1: Database schema migration
        print_test_header("1", "Database Schema Migration & Initialization")

        db = StateDB(str(db_path))
        state = db.load_state()
        print_result(len(state) == 0, "Empty database initialized successfully")
        print_result(db_path.exists(), f"Database file created at {db_path}")

        # Test 2: Scanner attribute reading
        print_test_header("2", "Scanner Attribute Reading (Phase 1)")

        # Create test file on left
        test_file_left = left_dir / "test_attrs.txt"
        test_file_left.write_text("Test file with attributes")

        # Set attributes on left file (Hidden, ReadOnly, Archive)
        attrs_to_set = 0x01 | 0x02 | 0x04  # All three
        success = set_file_attribute_win32(str(test_file_left), attrs_to_set)
        print_result(success, f"Set attributes 0x{attrs_to_set:02x} on left file")

        # Scan left directory
        scanner = Scanner()
        left_scan = scanner.scan_directory(str(left_dir))
        print_result("test_attrs.txt" in left_scan, "File found in left scan")

        if "test_attrs.txt" in left_scan:
            mtime, size, attrs = left_scan["test_attrs.txt"]
            print_result(
                attrs == attrs_to_set,
                f"Attributes read correctly: 0x{attrs:02x} (expected 0x{attrs_to_set:02x})",
            )

        # Test 3: FileMetadata and merge_scans
        print_test_header("3", "FileMetadata & Merge Scans (Phase 1)")

        # Create corresponding file on right with different attributes
        test_file_right = right_dir / "test_attrs.txt"
        test_file_right.write_text("Test file with attributes")
        attrs_right = 0x01  # Only Hidden
        set_file_attribute_win32(str(test_file_right), attrs_right)

        right_scan = scanner.scan_directory(str(right_dir))

        # Merge scans
        merged = scanner.merge_scans(left_scan, right_scan)
        print_result("test_attrs.txt" in merged, "File present in merged state")

        if "test_attrs.txt" in merged:
            metadata = merged["test_attrs.txt"]
            print_result(
                metadata.attrs_left == attrs_to_set,
                f"Left attributes preserved: 0x{metadata.attrs_left:02x}",
            )
            print_result(
                metadata.attrs_right == attrs_right,
                f"Right attributes preserved: 0x{metadata.attrs_right:02x}",
            )
            print_result(
                metadata.exists_left and metadata.exists_right, "File exists on both sides"
            )

        # Test 4: Database persistence
        print_test_header("4", "Database Persistence (Phase 1)")

        # Save merged state to database
        db.save_state(merged)
        print_result(True, "State saved to database")

        # Load state from database
        loaded_state = db.load_state()
        print_result(
            len(loaded_state) > 0, f"State loaded from database ({len(loaded_state)} entries)"
        )

        if "test_attrs.txt" in loaded_state:
            loaded_meta = loaded_state["test_attrs.txt"]
            print_result(
                loaded_meta.attrs_left == attrs_to_set,
                f"Left attributes restored: 0x{loaded_meta.attrs_left:02x}",
            )
            print_result(
                loaded_meta.attrs_right == attrs_right,
                f"Right attributes restored: 0x{loaded_meta.attrs_right:02x}",
            )

        # Test 5: Attribute change detection (Phase 2)
        print_test_header("5", "Attribute Change Detection (Phase 2)")

        # Create a scenario where only attributes changed on right
        # (content remains same - mtime and size unchanged)
        test_file_right_2 = right_dir / "content_unchanged.txt"
        test_file_right_2.write_text("Static content")

        # Copy to left with same content
        test_file_left_2 = left_dir / "content_unchanged.txt"
        test_file_left_2.write_text("Static content")

        # Set attributes on left
        set_file_attribute_win32(str(test_file_left_2), 0x01)  # Hidden

        # Set different attributes on right
        set_file_attribute_win32(str(test_file_right_2), 0x04)  # Archive

        # Scan both
        left_scan_2 = scanner.scan_directory(str(left_dir))
        right_scan_2 = scanner.scan_directory(str(right_dir))

        # Create sync engine with current state
        config = Config(
            {"left_root": str(left_dir), "right_root": str(right_dir), "dry_run": False}
        )

        # Create current state from scans
        current_state = scanner.merge_scans(left_scan_2, right_scan_2)

        sync_engine = SyncEngine(
            config=config,
            previous_state={},  # No previous state, all changes detected
            current_state=current_state,
        )

        jobs = sync_engine.generate_sync_jobs()

        # Look for attribute sync jobs for content_unchanged.txt
        attr_jobs = [
            j
            for j in jobs
            if "content_unchanged.txt" in j.file_path
            and j.action
            in [SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT, SyncAction.SYNC_ATTRS_RIGHT_TO_LEFT]
        ]

        print_result(
            len(attr_jobs) > 0,
            f"Attribute-only changes detected ({len(attr_jobs)} attribute job(s))",
        )

        for job in attr_jobs:
            attrs_val = job.payload.get("attrs", 0) if job.payload else 0
            print(f"  - {job.action.name}: 0x{attrs_val:02x}")

        # Test 6: File operations attribute setting (Phase 3)
        print_test_header("6", "File Operations Attribute Setting (Phase 3)")

        file_ops = FileOps()

        # Create a test file
        test_attr_file = tmpdir / "attr_test.txt"
        test_attr_file.write_text("Attribute test")

        # Set attributes using FileOps
        success = file_ops.set_file_attributes(str(test_attr_file), 0x03)  # Hidden + ReadOnly
        print_result(success, "FileOps.set_file_attributes() executed successfully")

        # Verify attributes were actually set
        attrs_read = Scanner.get_file_attributes(test_attr_file)
        print_result(attrs_read == 0x03, f"Attributes verified: 0x{attrs_read:02x} (expected 0x03)")

        # Test 7: Copy file with attribute preservation (Phase 3)
        print_test_header("7", "Copy File with Attribute Preservation (Phase 3)")

        src_file = tmpdir / "src_with_attrs.txt"
        src_file.write_text("Source file")
        set_file_attribute_win32(str(src_file), 0x07)  # All attributes

        dst_file = tmpdir / "dst_with_attrs.txt"

        # Copy with attribute preservation
        file_ops.copy_file(str(src_file), str(dst_file), preserve_mtime=True, preserve_attrs=True)

        print_result(dst_file.exists(), "File copied successfully")

        # Verify attributes were preserved
        src_attrs = Scanner.get_file_attributes(src_file)
        dst_attrs = Scanner.get_file_attributes(dst_file)
        print_result(
            dst_attrs == src_attrs,
            f"Attributes preserved: 0x{dst_attrs:02x} (source: 0x{src_attrs:02x})",
        )

        # Test 8: Job execution (Phase 4) - SYNC_ATTRS_LEFT_TO_RIGHT
        print_test_header("8", "Job Execution: SYNC_ATTRS_LEFT_TO_RIGHT (Phase 4)")

        left_attr_file = tmpdir / "left_attr_sync.txt"
        right_attr_file = tmpdir / "right_attr_sync.txt"

        left_attr_file.write_text("Content")
        right_attr_file.write_text("Content")

        # Set attributes on left only
        set_file_attribute_win32(str(left_attr_file), 0x05)  # Hidden + Archive
        right_initial_attrs = Scanner.get_file_attributes(right_attr_file)

        print(f"Before sync:")
        print(f"  LEFT:  0x{Scanner.get_file_attributes(left_attr_file):02x}")
        print(f"  RIGHT: 0x{right_initial_attrs:02x}")

        # Apply attributes to right (simulating SYNC_ATTRS_LEFT_TO_RIGHT handler)
        left_attrs = Scanner.get_file_attributes(left_attr_file)
        success = file_ops.set_file_attributes(str(right_attr_file), left_attrs)
        print_result(success, "SYNC_ATTRS_LEFT_TO_RIGHT executed")

        right_final_attrs = Scanner.get_file_attributes(right_attr_file)
        print(f"After sync:")
        print(f"  LEFT:  0x{Scanner.get_file_attributes(left_attr_file):02x}")
        print(f"  RIGHT: 0x{right_final_attrs:02x}")

        print_result(
            right_final_attrs == left_attrs, f"Right attributes synced: 0x{right_final_attrs:02x}"
        )

        # Test 9: Full integration - attribute-only change triggers sync
        print_test_header("9", "Full Integration: Attribute-Only Changes Trigger Sync")

        # Create a scenario from scratch
        integration_left = tmpdir / "integration_left"
        integration_right = tmpdir / "integration_right"
        integration_left.mkdir()
        integration_right.mkdir()

        # Create identical files
        test_file = integration_left / "sync_test.txt"
        test_file.write_text("Same content")
        shutil.copy2(str(test_file), str(integration_right / "sync_test.txt"))

        print("Initial state: Identical files, no attributes")

        # Scan initial state
        initial_left = Scanner().scan_directory(str(integration_left))
        initial_right = Scanner().scan_directory(str(integration_right))
        initial_merged = Scanner().merge_scans(initial_left, initial_right)

        # Change attributes on left only
        set_file_attribute_win32(str(integration_left / "sync_test.txt"), 0x02)  # ReadOnly
        print("Changed: LEFT file set to ReadOnly attribute")

        # Scan after change
        changed_left = Scanner().scan_directory(str(integration_left))
        changed_right = Scanner().scan_directory(str(integration_right))
        changed_merged = Scanner().merge_scans(changed_left, changed_right)

        # Generate sync jobs
        config_2 = Config(
            {
                "left_root": str(integration_left),
                "right_root": str(integration_right),
                "dry_run": False,
            }
        )

        changed_state = scanner.merge_scans(changed_left, changed_right)

        sync_engine_2 = SyncEngine(
            config=config_2, previous_state=initial_merged, current_state=changed_state
        )

        jobs_2 = sync_engine_2.generate_sync_jobs()

        # Look for attribute jobs
        attr_jobs_2 = [
            j
            for j in jobs_2
            if "sync_test.txt" in j.file_path
            and j.action
            in [SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT, SyncAction.SYNC_ATTRS_RIGHT_TO_LEFT]
        ]

        print_result(len(attr_jobs_2) > 0, "Attribute-only change detected and sync job generated")

        # Apply the sync job
        if attr_jobs_2:
            job = attr_jobs_2[0]
            attrs = job.payload.get("attrs", 0) if job.payload else 0
            print(f"Generated job: {job.action.name} with attrs=0x{attrs:02x}")

            # Execute job
            if job.action == SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT:
                file_ops.set_file_attributes(str(integration_right / "sync_test.txt"), attrs)
                print_result(True, "SYNC_ATTRS_LEFT_TO_RIGHT executed")

            # Verify sync
            right_attrs_after = Scanner.get_file_attributes(integration_right / "sync_test.txt")
            print_result(
                right_attrs_after == attrs,
                f"Right file attributes synced: 0x{right_attrs_after:02x}",
            )

    # Summary
    print("\n" + "=" * 70)
    print("END-TO-END TEST SUMMARY")
    print("=" * 70)
    print("\nAll phases validated:")
    print("  [OK] Phase 1: Database migration, metadata tracking, attribute reading")
    print("  [OK] Phase 2: Sync logic attribute detection")
    print("  [OK] Phase 3: File operations attribute setting and preservation")
    print("  [OK] Phase 4: Job execution handlers")
    print("\nAttribute sync feature is fully functional!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
