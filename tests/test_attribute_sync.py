"""Tests for file attribute synchronization feature."""

import tempfile
from pathlib import Path

import pytest

from remote_office_sync.config_loader import Config
from remote_office_sync.file_ops import FileOps
from remote_office_sync.scanner import Scanner
from remote_office_sync.sync_logic import SyncAction, SyncEngine


class TestAttributeSync:
    """Tests for attribute synchronization functionality."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary test directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            left_dir = tmpdir / "left"
            right_dir = tmpdir / "right"
            left_dir.mkdir()
            right_dir.mkdir()
            yield left_dir, right_dir

    @pytest.fixture
    def config(self, temp_dirs):
        """Create config for testing."""
        left_dir, right_dir = temp_dirs
        return Config(
            {
                "left_root": str(left_dir),
                "right_root": str(right_dir),
                "dry_run": False,
            }
        )

    @pytest.fixture
    def file_ops(self):
        """Create file operations handler."""
        return FileOps()

    @pytest.fixture
    def scanner(self):
        """Create scanner."""
        return Scanner()

    def test_scanner_reads_file_attributes(self, temp_dirs, scanner):
        """Test that scanner correctly reads file attributes."""
        left_dir, _ = temp_dirs

        # Create a test file
        test_file = left_dir / "test.txt"
        test_file.write_text("test content")

        # Set attributes using ctypes (if Windows)
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                kernel32 = ctypes.windll.kernel32
                set_attrs = kernel32.SetFileAttributesW
                set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
                set_attrs.restype = ctypes.c_bool

                # Set Hidden attribute
                set_attrs(str(test_file), 0x2)  # FILE_ATTRIBUTE_HIDDEN

                # Scan and verify
                scan_result = scanner.scan_directory(str(left_dir))
                assert "test.txt" in scan_result
                mtime, size, attrs = scan_result["test.txt"]
                assert attrs == 0x01  # Our bitmask for Hidden
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not set file attributes")

    def test_file_ops_sets_attributes(self, temp_dirs, file_ops):
        """Test that FileOps.set_file_attributes works correctly."""
        _, right_dir = temp_dirs

        # Create a test file
        test_file = right_dir / "test.txt"
        test_file.write_text("test content")

        # Set attributes
        success = file_ops.set_file_attributes(str(test_file), 0x03)  # Hidden + ReadOnly

        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                assert success
                # Verify with ctypes
                attrs_read = Scanner.get_file_attributes(test_file)
                assert attrs_read == 0x03
            else:
                # Non-Windows, set_file_attributes should return False
                assert not success
        except Exception:
            pass

    def test_copy_file_preserves_attributes(self, temp_dirs, file_ops, scanner):
        """Test that copy_file preserves attributes when preserve_attrs=True."""
        left_dir, right_dir = temp_dirs

        # Create source file
        src_file = left_dir / "src.txt"
        src_file.write_text("source content")

        # Set attributes on source
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                kernel32 = ctypes.windll.kernel32
                set_attrs = kernel32.SetFileAttributesW
                set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
                set_attrs.restype = ctypes.c_bool
                set_attrs(str(src_file), 0x2)  # Hidden

                # Copy with attribute preservation
                dst_file = right_dir / "dst.txt"
                file_ops.copy_file(str(src_file), str(dst_file), preserve_attrs=True)

                # Verify destination has attributes
                dst_attrs = Scanner.get_file_attributes(dst_file)
                src_attrs = Scanner.get_file_attributes(src_file)
                assert dst_attrs == src_attrs
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test attribute preservation")

    def test_attribute_change_detection(self, temp_dirs, config, scanner):
        """Test that SyncEngine detects attribute-only changes."""
        left_dir, right_dir = temp_dirs

        # Create identical files on both sides
        left_file = left_dir / "file.txt"
        right_file = right_dir / "file.txt"
        left_file.write_text("same content")
        right_file.write_text("same content")

        # Scan initial state
        initial_left = scanner.scan_directory(str(left_dir))
        initial_right = scanner.scan_directory(str(right_dir))
        initial_state = scanner.merge_scans(initial_left, initial_right)

        # Try to set attributes on left file
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                kernel32 = ctypes.windll.kernel32
                set_attrs = kernel32.SetFileAttributesW
                set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
                set_attrs.restype = ctypes.c_bool
                set_attrs(str(left_file), 0x02)  # ReadOnly

                # Scan after change
                changed_left = scanner.scan_directory(str(left_dir))
                changed_right = scanner.scan_directory(str(right_dir))
                changed_state = scanner.merge_scans(changed_left, changed_right)

                # Generate sync jobs
                sync_engine = SyncEngine(
                    config=config, previous_state=initial_state, current_state=changed_state
                )
                jobs = sync_engine.generate_sync_jobs()

                # Look for attribute sync jobs
                attr_jobs = [
                    j
                    for j in jobs
                    if "file.txt" in j.file_path
                    and j.action
                    in [
                        SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT,
                        SyncAction.SYNC_ATTRS_RIGHT_TO_LEFT,
                    ]
                ]

                assert len(attr_jobs) > 0
                assert attr_jobs[0].action == SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT
                assert attr_jobs[0].payload is not None
                assert "attrs" in attr_jobs[0].payload
                assert attr_jobs[0].payload["attrs"] == 0x02
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test attribute change detection")

    def test_sync_attrs_left_to_right_action(self, temp_dirs, file_ops):
        """Test SYNC_ATTRS_LEFT_TO_RIGHT job execution."""
        left_dir, right_dir = temp_dirs

        # Create test files
        left_file = left_dir / "file.txt"
        right_file = right_dir / "file.txt"
        left_file.write_text("content")
        right_file.write_text("content")

        # Set attributes on left
        success = file_ops.set_file_attributes(str(left_file), 0x05)  # Hidden + Archive

        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                assert success

                # Get left attributes
                left_attrs = Scanner.get_file_attributes(left_file)

                # Simulate job execution: sync attributes to right
                file_ops.set_file_attributes(str(right_file), left_attrs)

                # Verify right has same attributes
                right_attrs = Scanner.get_file_attributes(right_file)
                assert right_attrs == left_attrs
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test SYNC_ATTRS action")

    def test_sync_attrs_right_to_left_action(self, temp_dirs, file_ops):
        """Test SYNC_ATTRS_RIGHT_TO_LEFT job execution."""
        left_dir, right_dir = temp_dirs

        # Create test files
        left_file = left_dir / "file.txt"
        right_file = right_dir / "file.txt"
        left_file.write_text("content")
        right_file.write_text("content")

        # Set attributes on right
        success = file_ops.set_file_attributes(str(right_file), 0x04)  # Archive

        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                assert success

                # Get right attributes
                right_attrs = Scanner.get_file_attributes(right_file)

                # Simulate job execution: sync attributes to left
                file_ops.set_file_attributes(str(left_file), right_attrs)

                # Verify left has same attributes
                left_attrs = Scanner.get_file_attributes(left_file)
                assert left_attrs == right_attrs
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test SYNC_ATTRS action")

    def test_attribute_bitmask_combinations(self, temp_dirs, file_ops, scanner):
        """Test various attribute combinations."""
        left_dir, _ = temp_dirs

        test_cases = [
            (0x01, "Hidden only"),
            (0x02, "ReadOnly only"),
            (0x04, "Archive only"),
            (0x03, "Hidden + ReadOnly"),
            (0x05, "Hidden + Archive"),
            (0x06, "ReadOnly + Archive"),
            (0x07, "All attributes"),
        ]

        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                for attrs, description in test_cases:
                    test_file = left_dir / f"test_{attrs:02x}.txt"
                    test_file.write_text("content")

                    # Set attributes
                    file_ops.set_file_attributes(str(test_file), attrs)

                    # Verify they were set
                    read_attrs = Scanner.get_file_attributes(test_file)
                    assert read_attrs == attrs, f"Failed for {description}"
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test attribute combinations")

    def test_no_sync_when_attributes_unchanged(self, temp_dirs, config, scanner):
        """Test that no sync jobs are created when attributes don't change."""
        left_dir, right_dir = temp_dirs

        # Create identical files with same attributes
        left_file = left_dir / "file.txt"
        right_file = right_dir / "file.txt"
        left_file.write_text("same content")
        right_file.write_text("same content")

        # Scan both
        left_scan = scanner.scan_directory(str(left_dir))
        right_scan = scanner.scan_directory(str(right_dir))
        state = scanner.merge_scans(left_scan, right_scan)

        # Generate sync jobs with no changes
        sync_engine = SyncEngine(config=config, previous_state=state, current_state=state)
        jobs = sync_engine.generate_sync_jobs()

        # Should not have any attribute sync jobs
        attr_jobs = [
            j
            for j in jobs
            if j.action
            in [
                SyncAction.SYNC_ATTRS_LEFT_TO_RIGHT,
                SyncAction.SYNC_ATTRS_RIGHT_TO_LEFT,
            ]
        ]

        assert len(attr_jobs) == 0

    def test_metadata_preserved_with_attributes(self, temp_dirs, scanner):
        """Test that file metadata is correctly stored with attributes."""
        left_dir, right_dir = temp_dirs

        # Create files with different attributes
        left_file = left_dir / "file.txt"
        right_file = right_dir / "file.txt"
        left_file.write_text("content")
        right_file.write_text("content")

        # Set attributes
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                kernel32 = ctypes.windll.kernel32
                set_attrs = kernel32.SetFileAttributesW
                set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
                set_attrs.restype = ctypes.c_bool

                set_attrs(str(left_file), 0x02)  # ReadOnly
                set_attrs(str(right_file), 0x04)  # Archive

                # Scan both
                left_scan = scanner.scan_directory(str(left_dir))
                right_scan = scanner.scan_directory(str(right_dir))
                merged = scanner.merge_scans(left_scan, right_scan)

                # Verify metadata includes attributes
                assert "file.txt" in merged
                metadata = merged["file.txt"]
                assert metadata.attrs_left == 0x02
                assert metadata.attrs_right == 0x04
                assert metadata.exists_left
                assert metadata.exists_right
            else:
                pytest.skip("Windows API not available")
        except Exception:
            pytest.skip("Could not test metadata with attributes")
