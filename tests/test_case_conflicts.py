"""Unit tests for case conflict detection and resolution."""

import pytest

from remote_office_sync.config_loader import Config
from remote_office_sync.scanner import FileMetadata
from remote_office_sync.sync_logic import SyncAction, SyncEngine


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config(
        {
            "left_root": "/left",
            "right_root": "/right",
            "ignore": {},
            "soft_delete": {"enabled": True, "max_size_mb": 20},
            "conflict_policy": {
                "modify_modify": "clash",
                "new_new": "clash",
                "metadata_conflict": "clash",
            },
        }
    )


def test_case_conflict_both_sides_different_case(config):
    """Test case conflict when both sides rename to different cases."""
    # Previous state: file.txt on both sides
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current state: FILE.txt on left, File.txt on right
    current_state = {
        "FILE.txt": FileMetadata(
            relative_path="FILE.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=100.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
        "File.txt": FileMetadata(
            relative_path="File.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=100.0,
            size_left=None,
            size_right=10,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Should generate CASE_CONFLICT action
    conflict_jobs = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
    assert len(conflict_jobs) == 1
    assert conflict_jobs[0].file_path in ["File.txt", "FILE.txt"]


def test_case_change_one_side_only(config):
    """Test case change when only one side renames."""
    # Previous state: file.txt on both sides
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current state: FILE.txt on left (renamed), file.txt on right (unchanged)
    # Scanner would produce: FILE.txt with both sides, file.txt with right only
    current_state = {
        "FILE.txt": FileMetadata(
            relative_path="FILE.txt",
            exists_left=True,
            exists_right=True,  # Case-insensitive match
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        ),
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=False,
            exists_right=True,  # Actual right-side case
            mtime_left=None,
            mtime_right=100.0,
            size_left=None,
            size_right=10,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Should NOT generate RENAME_CONFLICT (only one side changed)
    conflict_jobs = [j for j in jobs if j.action == SyncAction.RENAME_CONFLICT]
    assert len(conflict_jobs) == 0

    # The one-side case change is detected as a simple case change, not a conflict
    # No rename jobs are generated as the file exists on both sides with same content
    # This is acceptable behavior - the file is accessible under both names on Windows


def test_no_conflict_both_sides_same_case(config):
    """Test no conflict when both sides rename to same case."""
    # Previous state: file.txt on both sides
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current state: FILE.txt on both sides (same case)
    current_state = {
        "FILE.txt": FileMetadata(
            relative_path="FILE.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Should NOT generate conflict (both changed to same case)
    conflict_jobs = [j for j in jobs if j.action == SyncAction.RENAME_CONFLICT]
    assert len(conflict_jobs) == 0


def test_case_conflict_in_subdirectory(config):
    """Test case conflict in subdirectory."""
    # Previous state: subdir/file.txt on both sides
    previous_state = {
        "subdir/file.txt": FileMetadata(
            relative_path="subdir/file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current state: subdir/FILE.txt on left, subdir/File.txt on right
    current_state = {
        "subdir/FILE.txt": FileMetadata(
            relative_path="subdir/FILE.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=100.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
        "subdir/File.txt": FileMetadata(
            relative_path="subdir/File.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=100.0,
            size_left=None,
            size_right=10,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Should generate CASE_CONFLICT action
    conflict_jobs = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
    assert len(conflict_jobs) == 1
    assert "subdir/" in conflict_jobs[0].file_path


def test_mixed_case_variations(config):
    """Test case conflict with mixed case variations."""
    # Previous state: file.txt on both sides
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current state: FiLe.txt on left, fIlE.txt on right (both different)
    current_state = {
        "FiLe.txt": FileMetadata(
            relative_path="FiLe.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=100.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
        "fIlE.txt": FileMetadata(
            relative_path="fIlE.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=100.0,
            size_left=None,
            size_right=10,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Should generate CASE_CONFLICT action
    conflict_jobs = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
    assert len(conflict_jobs) == 1


def test_case_conflict_three_variants_ignored(config):
    """Test that three simultaneous case variants do not crash and are ignored."""
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    # Current: three different case variants split across sides
    current_state = {
        "File.txt": FileMetadata(
            relative_path="File.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=110.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=110.0,
            size_left=None,
            size_right=10,
        ),
        "fILe.txt": FileMetadata(
            relative_path="fILe.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=105.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # Our detection only handles two variants; with three, no CASE_CONFLICT should be produced
    assert all(j.action != SyncAction.CASE_CONFLICT for j in jobs)
    assert all(j.action != SyncAction.RENAME_CONFLICT for j in jobs)


def test_conflict_files_are_ignored_for_case_detection(config):
    """Ensure files already named as conflict artifacts are not treated as case conflicts."""
    previous_state = {}
    current_state = {
        "Doc.CONFLICT.user.20250101.txt": FileMetadata(
            relative_path="Doc.CONFLICT.user.20250101.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=120.0,
            mtime_right=120.0,
            size_left=20,
            size_right=20,
        )
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    # No case-conflict or rename-conflict jobs should be generated for conflict artifacts
    assert all(j.action not in {SyncAction.CASE_CONFLICT, SyncAction.RENAME_CONFLICT} for j in jobs)


def test_case_conflict_right_newer(config):
    """Case conflict where right has newer mtime; expect CASE_CONFLICT job."""
    previous_state = {
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=10,
            size_right=10,
        )
    }

    current_state = {
        "FILE.txt": FileMetadata(
            relative_path="FILE.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=110.0,
            mtime_right=None,
            size_left=10,
            size_right=None,
        ),
        "file.txt": FileMetadata(
            relative_path="file.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=120.0,  # newer on right
            size_left=None,
            size_right=10,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    conflict_jobs = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
    assert len(conflict_jobs) == 1
    assert conflict_jobs[0].file_path in ["FILE.txt", "file.txt"]


def test_multiple_case_conflicts_in_one_run(config):
    """Ensure multiple independent case conflicts produce multiple jobs."""
    previous_state = {
        "a.txt": FileMetadata(
            relative_path="a.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=5,
            size_right=5,
        ),
        "b.txt": FileMetadata(
            relative_path="b.txt",
            exists_left=True,
            exists_right=True,
            mtime_left=100.0,
            mtime_right=100.0,
            size_left=5,
            size_right=5,
        ),
    }

    current_state = {
        "A.txt": FileMetadata(
            relative_path="A.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=110.0,
            mtime_right=None,
            size_left=5,
            size_right=None,
        ),
        "a.txt": FileMetadata(
            relative_path="a.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=110.0,
            size_left=None,
            size_right=5,
        ),
        "B.txt": FileMetadata(
            relative_path="B.txt",
            exists_left=True,
            exists_right=False,
            mtime_left=120.0,
            mtime_right=None,
            size_left=5,
            size_right=None,
        ),
        "b.txt": FileMetadata(
            relative_path="b.txt",
            exists_left=False,
            exists_right=True,
            mtime_left=None,
            mtime_right=120.0,
            size_left=None,
            size_right=5,
        ),
    }

    engine = SyncEngine(config, previous_state, current_state)
    jobs = engine.generate_sync_jobs()

    conflict_jobs = [j for j in jobs if j.action == SyncAction.CASE_CONFLICT]
    assert len(conflict_jobs) == 2
