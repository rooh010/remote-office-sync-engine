"""Tests for directory deletion feature."""

import pytest

from remote_office_sync.config_loader import Config
from remote_office_sync.scanner import FileMetadata
from remote_office_sync.sync_logic import SyncAction, SyncEngine


@pytest.fixture
def test_config():
    """Create test config."""
    return Config(
        {
            "left_root": "/tmp/left",
            "right_root": "/tmp/right",
            "soft_delete": {"enabled": True, "max_size_mb": 20},
            "conflict_policy": {
                "modify_modify": "clash",
                "new_new": "clash",
                "metadata_conflict": "clash",
            },
            "ignore": {},
        }
    )


class TestDirectoryDeletion:
    """Tests for directory deletion sync."""

    def test_delete_empty_directory_from_left(self, test_config):
        """Test that empty directory deleted from left is deleted from right."""
        # Directory exists on both sides in previous state
        previous = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=True,
                size_left=-1,  # -1 indicates directory
                size_right=-1,
            ),
        }
        # Directory no longer exists on left, still exists on right
        current = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=False,
                exists_right=True,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should generate DELETE_DIR_RIGHT action
        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.DELETE_DIR_RIGHT
        assert jobs[0].file_path == "mydir"

    def test_delete_empty_directory_from_right(self, test_config):
        """Test that empty directory deleted from right is deleted from left."""
        # Directory exists on both sides in previous state
        previous = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=True,
                size_left=-1,  # -1 indicates directory
                size_right=-1,
            ),
        }
        # Directory no longer exists on right, still exists on left
        current = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=False,
                size_left=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should generate DELETE_DIR_LEFT action
        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.DELETE_DIR_LEFT
        assert jobs[0].file_path == "mydir"

    def test_dont_delete_directory_with_files(self, test_config):
        """Test that directory with files is NOT deleted just because it's on one side."""
        # Directory exists on left with file, doesn't exist on right
        previous = {}
        current = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=False,
                size_left=-1,
            ),
            "mydir/file.txt": FileMetadata(
                relative_path="mydir/file.txt",
                exists_left=True,
                exists_right=False,
                size_left=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should create directory on right, not delete
        dir_jobs = [j for j in jobs if j.file_path == "mydir"]
        assert len(dir_jobs) == 1
        assert dir_jobs[0].action == SyncAction.CREATE_DIR_RIGHT

    def test_nested_directory_deletion(self, test_config):
        """Test that nested directories are deleted when user deletes parent."""
        # Multiple nested directories exist on both sides
        previous = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=True,
                size_left=-1,
                size_right=-1,
            ),
            "mydir/subdir": FileMetadata(
                relative_path="mydir/subdir",
                exists_left=True,
                exists_right=True,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Both directories deleted from left
        current = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=False,
                exists_right=True,
                size_right=-1,
            ),
            "mydir/subdir": FileMetadata(
                relative_path="mydir/subdir",
                exists_left=False,
                exists_right=True,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should generate DELETE_DIR_RIGHT for both directories
        delete_jobs = [j for j in jobs if j.action == SyncAction.DELETE_DIR_RIGHT]
        assert len(delete_jobs) == 2
        assert any(j.file_path == "mydir" for j in delete_jobs)
        assert any(j.file_path == "mydir/subdir" for j in delete_jobs)

    def test_dont_delete_new_empty_directory(self, test_config):
        """Test that new empty directory on one side is NOT deleted."""
        previous = {}
        # New empty directory only on right
        current = {
            "newdir": FileMetadata(
                relative_path="newdir",
                exists_left=False,
                exists_right=True,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should create directory on left, not delete from right
        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.CREATE_DIR_LEFT
        assert jobs[0].file_path == "newdir"

    def test_directory_deleted_from_both_sides(self, test_config):
        """Test directory that was deleted from both sides (edge case)."""
        # Directory exists on both sides in previous state
        previous = {
            "mydir": FileMetadata(
                relative_path="mydir",
                exists_left=True,
                exists_right=True,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Directory is gone from both sides (not in current state)
        current = {}

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should generate DELETE_DIR actions for both sides (handled by deletion detection loop)
        # This cleans up the directory entries from the state database
        assert len(jobs) == 2
        delete_jobs = [
            j for j in jobs if j.action in (SyncAction.DELETE_DIR_LEFT, SyncAction.DELETE_DIR_RIGHT)
        ]
        assert len(delete_jobs) == 2
        assert any(j.action == SyncAction.DELETE_DIR_LEFT for j in delete_jobs)
        assert any(j.action == SyncAction.DELETE_DIR_RIGHT for j in delete_jobs)
