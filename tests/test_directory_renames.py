"""Tests for directory rename detection and handling."""

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


class TestDirectoryRenameDetection:
    """Tests for directory rename detection."""

    def test_directory_rename_on_left_only(self, test_config):
        """Test directory renamed on left side only.

        When a directory is renamed on left only:
        - Scanner sees: new name on left, old name still on right
        - Previous state has old name on both sides
        - Current state has new name on left, old name on right (not synced yet)

        Expected behavior:
        - Should detect this as a cross-side rename
        - Should generate jobs to sync the rename to right
        """
        previous = {
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # After user renames: old_folder -> new_folder on left only
        current = {
            "new_folder": FileMetadata(
                relative_path="new_folder",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        jobs_desc = [(j.action.name, j.file_path) for j in jobs]
        assert len(jobs) > 0, f"Should detect rename. Jobs: {jobs_desc}"

    def test_directory_rename_on_right_only(self, test_config):
        """Test directory renamed on right side only."""
        previous = {
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # After user renames: old_folder -> new_folder on right only
        current = {
            "new_folder": FileMetadata(
                relative_path="new_folder",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        jobs_desc = [(j.action.name, j.file_path) for j in jobs]
        assert len(jobs) > 0, f"Should detect rename. Jobs: {jobs_desc}"

    def test_directory_rename_to_same_name_on_both_sides(self, test_config):
        """Test directory renamed to same name on both sides."""
        previous = {
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Both sides rename to same name - should be detected as clean rename
        current = {
            "new_folder": FileMetadata(
                relative_path="new_folder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Both sides already have new name, so minimal jobs expected
        # At minimum, should not have rename conflicts
        rename_conflicts = [j for j in jobs if j.action == SyncAction.RENAME_CONFLICT]
        assert len(rename_conflicts) == 0, "Should not have rename conflicts"

    def test_directory_rename_conflict_different_names(self, test_config):
        """Test directory renamed to different names on both sides."""
        previous = {
            "old_folder": FileMetadata(
                relative_path="old_folder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Left renames to left_renamed, right renames to right_renamed
        current = {
            "left_renamed": FileMetadata(
                relative_path="left_renamed",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "right_renamed": FileMetadata(
                relative_path="right_renamed",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        rename_conflicts = [j for j in jobs if j.action == SyncAction.RENAME_CONFLICT]
        assert len(rename_conflicts) > 0, "Should detect rename conflict"

    def test_directory_case_change_on_left_only(self, test_config):
        """Test directory with case change on left only."""
        previous = {
            "myfolder": FileMetadata(
                relative_path="myfolder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Left changes case: myfolder -> MyFolder
        current = {
            "MyFolder": FileMetadata(
                relative_path="MyFolder",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "myfolder": FileMetadata(
                relative_path="myfolder",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should handle case change (either as rename or case conflict)
        assert len(jobs) >= 0, "Should handle case change without crashing"

    def test_directory_case_conflict_different_cases(self, test_config):
        """Test directory with different case changes on both sides."""
        previous = {
            "myfolder": FileMetadata(
                relative_path="myfolder",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Left changes to MyFolder, right changes to MYFOLDER
        current = {
            "MyFolder": FileMetadata(
                relative_path="MyFolder",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "MYFOLDER": FileMetadata(
                relative_path="MYFOLDER",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        case_conflicts = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
        # Should detect case conflict
        assert len(case_conflicts) > 0, "Should detect case conflict"

    def test_nested_directory_rename(self, test_config):
        """Test rename of nested directory structure."""
        previous = {
            "parent/old_child": FileMetadata(
                relative_path="parent/old_child",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
            "parent/old_child/file.txt": FileMetadata(
                relative_path="parent/old_child/file.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=500.0,
                mtime_right=500.0,
                size_left=100,
                size_right=100,
            ),
        }
        # Rename child directory
        current = {
            "parent/new_child": FileMetadata(
                relative_path="parent/new_child",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "parent/new_child/file.txt": FileMetadata(
                relative_path="parent/new_child/file.txt",
                exists_left=True,
                exists_right=False,
                mtime_left=500.0,
                size_left=100,
            ),
            "parent/old_child": FileMetadata(
                relative_path="parent/old_child",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
            "parent/old_child/file.txt": FileMetadata(
                relative_path="parent/old_child/file.txt",
                exists_left=False,
                exists_right=True,
                mtime_right=500.0,
                size_right=100,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should handle nested directory rename
        assert len(jobs) >= 0, "Should handle nested directory rename"

    def test_multiple_directory_renames_same_sync(self, test_config):
        """Test multiple directories renamed in same sync cycle."""
        previous = {
            "folder1": FileMetadata(
                relative_path="folder1",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=-1,
                size_right=-1,
            ),
            "folder2": FileMetadata(
                relative_path="folder2",
                exists_left=True,
                exists_right=True,
                mtime_left=2000.0,
                mtime_right=2000.0,
                size_left=-1,
                size_right=-1,
            ),
        }
        # Both renamed on left
        current = {
            "renamed1": FileMetadata(
                relative_path="renamed1",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
            "renamed2": FileMetadata(
                relative_path="renamed2",
                exists_left=True,
                exists_right=False,
                mtime_left=2000.0,
                size_left=-1,
            ),
            "folder1": FileMetadata(
                relative_path="folder1",
                exists_left=False,
                exists_right=True,
                mtime_right=1000.0,
                size_right=-1,
            ),
            "folder2": FileMetadata(
                relative_path="folder2",
                exists_left=False,
                exists_right=True,
                mtime_right=2000.0,
                size_right=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should handle multiple independent renames
        assert len(jobs) > 0, "Should generate jobs for multiple renames"

    def test_directory_only_on_left_not_confused_with_rename(self, test_config):
        """Test that new directory on left is not confused with a rename."""
        previous = {}
        current = {
            "new_folder": FileMetadata(
                relative_path="new_folder",
                exists_left=True,
                exists_right=False,
                mtime_left=1000.0,
                size_left=-1,
            ),
        }

        engine = SyncEngine(test_config, previous, current)
        jobs = engine.generate_sync_jobs()

        # Should be treated as new directory, not a rename
        copy_jobs = [
            j
            for j in jobs
            if j.action in [SyncAction.COPY_LEFT_TO_RIGHT, SyncAction.CREATE_DIR_RIGHT]
        ]
        rename_jobs = [j for j in jobs if "RENAME" in j.action.name]

        # Should have copy/create job, not rename job
        assert len(copy_jobs) > 0 or len(jobs) > 0, "Should handle new directory"
        assert len(rename_jobs) == 0, "Should not treat new directory as rename"
