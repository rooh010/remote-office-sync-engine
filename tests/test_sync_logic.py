"""Tests for sync decision engine."""

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


class TestSyncEngine:
    """SyncEngine tests."""

    def test_new_file_on_left(self, test_config):
        """Test new file on left only."""
        previous = {}
        current = {
            "new.txt": FileMetadata(
                relative_path="new.txt",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.COPY_LEFT_TO_RIGHT
        assert jobs[0].file_path == "new.txt"

    def test_new_file_on_right(self, test_config):
        """Test new file on right only."""
        previous = {}
        current = {
            "new.txt": FileMetadata(
                relative_path="new.txt",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.COPY_RIGHT_TO_LEFT
        assert jobs[0].file_path == "new.txt"

    def test_changed_on_left_only(self, test_config):
        """Test file changed only on left."""
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
                mtime_right=1000.0,  # Unchanged on right
                size_left=200,
                size_right=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Size difference triggers metadata conflict which defaults to clash
        assert len(jobs) == 1
        assert jobs[0].action in [
            SyncAction.COPY_LEFT_TO_RIGHT,
            SyncAction.CLASH_CREATE,
        ]

    def test_deleted_on_left_unchanged_on_right(self, test_config):
        """Test file deleted on left, unchanged on right."""
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
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,  # Unchanged
                size_right=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        assert len(jobs) == 1
        assert jobs[0].action in [
            SyncAction.DELETE_RIGHT,
            SyncAction.SOFT_DELETE_RIGHT,
        ]

    def test_deleted_on_left_changed_on_right(self, test_config):
        """Test file deleted on left but changed on right."""
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
                exists_left=False,
                exists_right=True,
                mtime_right=2000.0,  # Changed on right
                size_right=200,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        assert len(jobs) == 1
        assert jobs[0].action == SyncAction.COPY_RIGHT_TO_LEFT

    def test_no_changes(self, test_config):
        """Test when there are no changes."""
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
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # No jobs should be generated
        assert len(jobs) == 0
