"""Tests for the scanner module."""

from remote_office_sync.scanner import Scanner


class TestScanner:
    """Scanner tests."""

    def test_scan_empty_directory(self, temp_dirs):
        """Test scanning empty directory."""
        left, _ = temp_dirs
        scanner = Scanner()

        result = scanner.scan_directory(str(left))
        assert result == {}

    def test_scan_single_file(self, temp_dirs):
        """Test scanning directory with single file."""
        left, _ = temp_dirs
        test_file = left / "test.txt"
        test_file.write_text("content")

        scanner = Scanner()
        result = scanner.scan_directory(str(left))

        assert "test.txt" in result
        assert result["test.txt"][1] == 7  # size is 7 bytes

    def test_scan_nested_files(self, temp_dirs):
        """Test scanning nested directory structure."""
        left, _ = temp_dirs
        subdir = left / "subdir"
        subdir.mkdir()
        (subdir / "file1.txt").write_text("data1")
        (left / "file2.txt").write_text("data2")

        scanner = Scanner()
        result = scanner.scan_directory(str(left))

        assert "file2.txt" in result
        assert "subdir/file1.txt" in result or "subdir\\file1.txt" in result

    def test_ignore_extensions(self, temp_dirs):
        """Test ignoring files by extension."""
        left, _ = temp_dirs
        (left / "keep.txt").write_text("keep")
        (left / "ignore.tmp").write_text("ignore")
        (left / "ignore.bak").write_text("ignore")

        scanner = Scanner(ignore_extensions=[".tmp", ".bak"])
        result = scanner.scan_directory(str(left))

        assert "keep.txt" in result
        assert "ignore.tmp" not in result
        assert "ignore.bak" not in result

    def test_ignore_prefix(self, temp_dirs):
        """Test ignoring files by prefix."""
        left, _ = temp_dirs
        (left / "normal.txt").write_text("keep")
        (left / ".hidden").write_text("ignore")
        (left / "__pycache__").write_text("ignore")

        scanner = Scanner(ignore_filenames_prefix=[".", "__"])
        result = scanner.scan_directory(str(left))

        assert "normal.txt" in result
        assert ".hidden" not in result
        assert "__pycache__" not in result

    def test_ignore_exact(self, temp_dirs):
        """Test ignoring files by exact name."""
        left, _ = temp_dirs
        (left / "keep.txt").write_text("keep")
        (left / "thumbs.db").write_text("ignore")

        scanner = Scanner(ignore_filenames_exact=["thumbs.db"])
        result = scanner.scan_directory(str(left))

        assert "keep.txt" in result
        assert "thumbs.db" not in result

    def test_merge_scans(self, temp_dirs):
        """Test merging left and right scans."""
        left, right = temp_dirs
        (left / "left_only.txt").write_text("left")
        (right / "right_only.txt").write_text("right")
        (left / "both.txt").write_text("left_content")
        (right / "both.txt").write_text("right_content")

        scanner = Scanner()
        left_scan = scanner.scan_directory(str(left))
        right_scan = scanner.scan_directory(str(right))

        merged = scanner.merge_scans(left_scan, right_scan)

        # Find paths with flexible separators
        left_only_path = next((p for p in merged if "left_only" in p), None)
        right_only_path = next((p for p in merged if "right_only" in p), None)
        both_path = next((p for p in merged if p == "both.txt"), None)

        assert left_only_path
        assert merged[left_only_path].exists_left
        assert not merged[left_only_path].exists_right

        assert right_only_path
        assert not merged[right_only_path].exists_left
        assert merged[right_only_path].exists_right

        assert both_path
        assert merged[both_path].exists_left
        assert merged[both_path].exists_right
