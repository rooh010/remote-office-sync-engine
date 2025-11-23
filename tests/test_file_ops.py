"""Tests for file operations module."""

from pathlib import Path

import pytest

from remote_office_sync.file_ops import FileOps, FileOpsError


class TestFileOps:
    """FileOps tests."""

    def test_copy_file(self, temp_dirs):
        """Test copying a file."""
        left, right = temp_dirs
        src_file = left / "source.txt"
        src_file.write_text("content")

        file_ops = FileOps()
        dst_file = right / "dest.txt"

        file_ops.copy_file(str(src_file), str(dst_file))

        assert dst_file.exists()
        assert dst_file.read_text() == "content"

    def test_copy_file_creates_directories(self, temp_dirs):
        """Test that copy_file creates destination directories."""
        left, right = temp_dirs
        src_file = left / "source.txt"
        src_file.write_text("content")

        file_ops = FileOps()
        dst_file = right / "subdir" / "nested" / "dest.txt"

        file_ops.copy_file(str(src_file), str(dst_file))

        assert dst_file.exists()

    def test_delete_file_hard(self, temp_dirs):
        """Test hard delete."""
        left, _ = temp_dirs
        test_file = left / "delete_me.txt"
        test_file.write_text("content")

        file_ops = FileOps()
        file_ops.delete_file(str(test_file), soft=False)

        assert not test_file.exists()

    def test_delete_file_soft(self, temp_dirs):
        """Test soft delete."""
        left, right = temp_dirs
        test_file = left / "delete_me.txt"
        test_file.write_text("content")

        file_ops = FileOps(soft_delete_root=str(right / ".deleted"))
        file_ops.delete_file(str(test_file), soft=True)

        assert not test_file.exists()
        # Check that file was moved to soft delete directory
        deleted_dir = right / ".deleted"
        assert deleted_dir.exists()
        assert len(list(deleted_dir.rglob("*"))) > 0

    def test_soft_delete_respects_size_limit(self, temp_dirs):
        """Test that soft delete respects size limit."""
        left, right = temp_dirs
        large_file = left / "large.bin"
        # Create 21 MB file (exceeds 20 MB default)
        large_file.write_bytes(b"x" * (21 * 1024 * 1024))

        file_ops = FileOps(soft_delete_root=str(right / ".deleted"))
        file_ops.delete_file(str(large_file), soft=True, max_size_bytes=20 * 1024 * 1024)

        # Should be hard deleted, not soft deleted
        assert not large_file.exists()
        deleted_dir = right / ".deleted"
        if deleted_dir.exists():
            assert len(list(deleted_dir.rglob("*"))) == 0

    def test_rename_file(self, temp_dirs):
        """Test renaming a file."""
        left, _ = temp_dirs
        old_file = left / "old_name.txt"
        old_file.write_text("content")

        file_ops = FileOps()
        new_file = left / "new_name.txt"

        file_ops.rename_file(str(old_file), str(new_file))

        assert not old_file.exists()
        assert new_file.exists()
        assert new_file.read_text() == "content"

    def test_create_clash_file(self, temp_dirs):
        """Test creating conflict file."""
        left, _ = temp_dirs
        original = left / "conflict.txt"
        original.write_text("content")

        file_ops = FileOps()
        conflict_path = file_ops.create_clash_file(str(original), is_left=True)

        assert Path(conflict_path).exists()
        assert "conflict" in conflict_path.lower()
        assert original.read_text() == "content"

    def test_ensure_directory(self, temp_dirs):
        """Test ensuring directory exists."""
        left, _ = temp_dirs
        nested_dir = left / "a" / "b" / "c"

        file_ops = FileOps()
        file_ops.ensure_directory(str(nested_dir))

        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_copy_nonexistent_file(self, temp_dirs):
        """Test copying non-existent file raises error."""
        left, right = temp_dirs

        file_ops = FileOps()
        with pytest.raises(FileOpsError):
            file_ops.copy_file(str(left / "nonexistent.txt"), str(right / "dest.txt"))
