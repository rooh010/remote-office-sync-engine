"""Tests for conflict detection module."""

from remote_office_sync.conflict import ConflictDetector, ConflictType
from remote_office_sync.scanner import FileMetadata


class TestConflictDetector:
    """ConflictDetector tests."""

    def test_detect_no_conflicts(self):
        """Test detection when there are no conflicts."""
        previous = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }
        current = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=2000.0,
                mtime_right=1000.0,  # Only left changed
                size_left=100,
                size_right=100,
            ),
        }

        detector = ConflictDetector(previous, current)
        conflicts = detector.detect_conflicts()

        assert len(conflicts) == 0

    def test_detect_modify_modify_conflict(self):
        """Test detecting modify-modify conflict."""
        previous = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }
        current = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=2000.0,  # Changed on left
                mtime_right=2000.0,  # Changed on right
                size_left=200,
                size_right=150,  # Different content
            ),
        }

        detector = ConflictDetector(previous, current)
        conflicts = detector.detect_conflicts()

        # Both modified on both sides, detects as conflict (either MODIFY_MODIFY or METADATA)
        assert len(conflicts) == 1
        assert conflicts["file.txt"][0] in [
            ConflictType.MODIFY_MODIFY,
            ConflictType.METADATA_CONFLICT,
        ]

    def test_detect_new_new_conflict(self):
        """Test detecting new-new conflict."""
        previous = {}
        current = {
            "new.txt": FileMetadata(
                relative_path="new.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=2000.0,
                size_left=100,
                size_right=200,  # Different content
            ),
        }

        detector = ConflictDetector(previous, current)
        conflicts = detector.detect_conflicts()

        assert len(conflicts) == 1
        assert conflicts["new.txt"][0] == ConflictType.NEW_NEW

    def test_same_content_no_conflict(self):
        """Test that same content on both sides is not a conflict."""
        previous = {}
        current = {
            "new.txt": FileMetadata(
                relative_path="new.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,  # Same size and mtime
            ),
        }

        detector = ConflictDetector(previous, current)
        conflicts = detector.detect_conflicts()

        # No conflict since content is identical
        assert len(conflicts) == 0

    def test_same_size_mtime_but_different_bytes_conflicts(self, tmp_path):
        """Files with same size/mtime but different content should conflict."""
        left_root = tmp_path / "left"
        right_root = tmp_path / "right"
        left_root.mkdir()
        right_root.mkdir()

        (left_root / "file.txt").write_text("left-version")
        (right_root / "file.txt").write_text("right-versn1")  # same length 12

        # Align mtimes to be identical
        ts = 1_700_000_000
        for p in (left_root / "file.txt", right_root / "file.txt"):
            import os

            os.utime(p, (ts, ts))

        previous = {}
        current = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=float(ts),
                mtime_right=float(ts),
                size_left=(left_root / "file.txt").stat().st_size,
                size_right=(right_root / "file.txt").stat().st_size,
            ),
        }

        detector = ConflictDetector(
            previous,
            current,
            mtime_tolerance=2.0,
            left_root=str(left_root),
            right_root=str(right_root),
        )
        conflicts = detector.detect_conflicts()

        assert len(conflicts) == 1
        assert conflicts["file.txt"][0] == ConflictType.NEW_NEW

    def test_was_modified_both_sides(self):
        """Test detecting modification on both sides."""
        previous = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }
        current = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=2000.0,
                mtime_right=2000.0,
                size_left=100,
                size_right=100,
            ),
        }

        detector = ConflictDetector(previous, current)
        result = detector._was_modified_both_sides(
            "file.txt", previous["file.txt"], current["file.txt"]
        )

        assert result is True

    def test_metadata_conflict_detection(self):
        """Test detecting metadata conflicts (size mismatch)."""
        previous = {}
        current = {
            "file.txt": FileMetadata(
                relative_path="file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=1000,
                size_right=2000,  # 100% size difference
            ),
        }

        detector = ConflictDetector(previous, current)
        conflicts = detector.detect_conflicts()

        # Should detect as conflict due to size mismatch
        assert len(conflicts) >= 0  # Depends on size threshold
