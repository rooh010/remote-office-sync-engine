"""Tests for the conflict-handling logic inside SyncRunner._execute_job."""

import os
from types import SimpleNamespace

import pytest

from remote_office_sync.config_loader import Config
from remote_office_sync.file_ops import FileOps
from remote_office_sync.main import SyncRunner
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncAction


@pytest.fixture
def runner(tmp_path):
    """Create a SyncRunner-like object with temporary roots."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    config = Config(
        {
            "left_root": str(left),
            "right_root": str(right),
            "dry_run": False,
            "soft_delete": {"enabled": False},
            "conflict_policy": {
                "modify_modify": "clash",
                "new_new": "clash",
                "metadata_conflict": "clash",
            },
            "ignore": {},
        }
    )

    instance = SyncRunner.__new__(SyncRunner)
    instance.config = config
    instance.file_ops = FileOps(soft_delete_root=str(tmp_path / ".deleted"))
    instance.state_db = StateDB(str(tmp_path / "state.db"))
    instance.username = "UnitTestUser"
    instance.conflict_alerts = []
    instance.error_alerts = []
    instance.content_conflicts_detected = False

    return instance, left, right


def test_clash_create_keeps_newer_main_and_conflicts_on_both_sides(runner):
    """CLASH_CREATE should keep the newer file as main and copy conflict artifacts to both roots."""
    instance, left_root, right_root = runner
    left_file = left_root / "conflict.txt"
    right_file = right_root / "conflict.txt"

    left_file.write_text("newer-left")
    right_file.write_text("older-right")

    newer_ts = 1_700_000_100
    older_ts = newer_ts - 100
    os.utime(left_file, (newer_ts, newer_ts))
    os.utime(right_file, (older_ts, older_ts))

    job = SimpleNamespace(
        action=SyncAction.CLASH_CREATE,
        file_path="conflict.txt",
        details="modify",
    )

    assert instance._execute_job(job) is True

    # Main file should contain the newer content on both sides
    assert left_file.read_text() == "newer-left"
    assert right_file.read_text() == "newer-left"

    # Conflict files should exist on both sides with the older content
    left_conflicts = list(left_root.glob("conflict.CONFLICT.UnitTestUser.*.txt"))
    right_conflicts = list(right_root.glob("conflict.CONFLICT.UnitTestUser.*.txt"))

    assert len(left_conflicts) == 1
    assert len(right_conflicts) == 1
    assert left_conflicts[0].name == right_conflicts[0].name
    assert left_conflicts[0].read_text() == "older-right"
    assert right_conflicts[0].read_text() == "older-right"

    assert instance.content_conflicts_detected is True
    assert instance.conflict_alerts, "Conflicts should be recorded for notify/logging"


def test_case_conflict_keeps_newer_casing_and_conflict_artifacts(runner):
    """CASE_CONFLICT should keep the newer casing/content and replicate conflict copies."""
    instance, left_root, right_root = runner
    left_file = left_root / "CaseTest.txt"
    right_file = right_root / "casetest.txt"

    left_file.write_text("older-left-case")
    right_file.write_text("NEW-RIGHT-CONTENT")

    left_ts = 1_700_000_000
    right_ts = left_ts + 60
    os.utime(left_file, (left_ts, left_ts))
    os.utime(right_file, (right_ts, right_ts))

    job = SimpleNamespace(
        action=SyncAction.CASE_CONFLICT,
        file_path="CaseTest.txt",
        src_path="casetest.txt",
        payload={"left_mtime": float(left_ts), "right_mtime": float(right_ts)},
    )

    assert instance._execute_job(job) is True

    canonical_left = left_root / "casetest.txt"
    canonical_right = right_root / "casetest.txt"

    assert canonical_left.exists()
    assert canonical_right.exists()
    assert canonical_left.read_text() == "NEW-RIGHT-CONTENT"
    assert canonical_right.read_text() == "NEW-RIGHT-CONTENT"

    conflict_glob = "CaseTest.CONFLICT.UnitTestUser.*.txt"
    left_conflicts = list(left_root.glob(conflict_glob))
    right_conflicts = list(right_root.glob(conflict_glob))

    assert len(left_conflicts) == 1
    assert len(right_conflicts) == 1
    assert left_conflicts[0].name == right_conflicts[0].name
    expected_older = "older-left-case"
    assert left_conflicts[0].read_text() == expected_older
    assert right_conflicts[0].read_text() == expected_older

    # Directory listing should only show the canonical case variant + conflicts
    left_names = {p.name for p in left_root.iterdir()}
    assert "casetest.txt" in left_names
    assert "CaseTest.txt" not in left_names

    assert instance.content_conflicts_detected is False
    assert instance.conflict_alerts, "Case conflict should emit alert metadata"


def test_clash_create_preserves_directory_structure(runner):
    """CLASH_CREATE should place conflict files in same directory as original files."""
    instance, left_root, right_root = runner

    # Create subdirectories and files
    left_subdir = left_root / "subdir" / "nested"
    right_subdir = right_root / "subdir" / "nested"
    left_subdir.mkdir(parents=True)
    right_subdir.mkdir(parents=True)

    left_file = left_subdir / "conflict.txt"
    right_file = right_subdir / "conflict.txt"

    left_file.write_text("newer-left")
    right_file.write_text("older-right")

    newer_ts = 1_700_000_100
    older_ts = newer_ts - 100
    os.utime(left_file, (newer_ts, newer_ts))
    os.utime(right_file, (older_ts, older_ts))

    job = SimpleNamespace(
        action=SyncAction.CLASH_CREATE,
        file_path="subdir/nested/conflict.txt",
        details="modify",
    )

    assert instance._execute_job(job) is True

    # Main files should have newer content
    assert left_file.read_text() == "newer-left"
    assert right_file.read_text() == "newer-left"

    # Conflict files should be in the SAME subdirectory, not at root
    left_conflicts = list(left_subdir.glob("conflict.CONFLICT.UnitTestUser.*.txt"))
    right_conflicts = list(right_subdir.glob("conflict.CONFLICT.UnitTestUser.*.txt"))

    assert len(left_conflicts) == 1, "Conflict file should exist in left subdirectory"
    assert len(right_conflicts) == 1, "Conflict file should exist in right subdirectory"
    assert left_conflicts[0].name == right_conflicts[0].name
    assert left_conflicts[0].read_text() == "older-right"
    assert right_conflicts[0].read_text() == "older-right"

    # Verify NO conflicts at root level
    root_left_conflicts = list(left_root.glob("conflict.CONFLICT*.txt"))
    root_right_conflicts = list(right_root.glob("conflict.CONFLICT*.txt"))
    assert len(root_left_conflicts) == 0, "Conflict should not be at root level"
    assert len(root_right_conflicts) == 0, "Conflict should not be at root level"
