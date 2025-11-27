"""Tests for dry run formatter."""

from remote_office_sync.dry_run_formatter import DryRunFormatter
from remote_office_sync.sync_logic import SyncAction, SyncJob


def test_format_no_changes():
    """Test formatting when no changes are needed."""
    formatter = DryRunFormatter()
    output = formatter.format_dry_run_output([])

    assert "DRY RUN MODE" in output
    assert "NO CHANGES WILL BE MADE" in output
    assert "No synchronization needed" in output


def test_format_copy_jobs():
    """Test formatting copy operations."""
    formatter = DryRunFormatter()
    jobs = [
        SyncJob(file_path="test.txt", action=SyncAction.COPY_LEFT_TO_RIGHT),
        SyncJob(file_path="doc.pdf", action=SyncAction.COPY_RIGHT_TO_LEFT),
    ]

    output = formatter.format_dry_run_output(jobs)

    assert "DRY RUN MODE" in output
    assert "2 operations would be performed" in output
    assert "test.txt" in output
    assert "doc.pdf" in output
    assert "→" in output  # Left to right arrow
    assert "←" in output  # Right to left arrow


def test_format_delete_jobs():
    """Test formatting delete operations."""
    formatter = DryRunFormatter()
    jobs = [
        SyncJob(file_path="old.txt", action=SyncAction.SOFT_DELETE_LEFT),
        SyncJob(file_path="temp.dat", action=SyncAction.DELETE_RIGHT),
    ]

    output = formatter.format_dry_run_output(jobs)

    assert "old.txt" in output
    assert "temp.dat" in output
    assert "Soft delete" in output or "⊗" in output
    assert "delete" in output.lower()


def test_format_conflict_jobs():
    """Test formatting conflict operations."""
    formatter = DryRunFormatter()
    jobs = [SyncJob(file_path="conflict.txt", action=SyncAction.CLASH_CREATE)]

    output = formatter.format_dry_run_output(jobs)

    assert "conflict.txt" in output
    assert "Conflict" in output or "⚠" in output


def test_grouping_by_action():
    """Test that jobs are grouped by action type."""
    formatter = DryRunFormatter()
    jobs = [
        SyncJob(file_path="file1.txt", action=SyncAction.COPY_LEFT_TO_RIGHT),
        SyncJob(file_path="file2.txt", action=SyncAction.COPY_LEFT_TO_RIGHT),
        SyncJob(file_path="file3.txt", action=SyncAction.SOFT_DELETE_LEFT),
    ]

    output = formatter.format_dry_run_output(jobs)

    assert "Summary by Action" in output
    assert "Copy LEFT → RIGHT: 2 files" in output
    assert "Soft delete from LEFT: 1 files" in output


def test_custom_side_names():
    """Test using custom names for left and right sides."""
    formatter = DryRunFormatter(left_name="LOCAL", right_name="REMOTE")
    jobs = [SyncJob(file_path="test.txt", action=SyncAction.COPY_LEFT_TO_RIGHT)]

    output = formatter.format_dry_run_output(jobs)

    # Custom names should appear in the diagram
    assert "[LOCAL]" in output
    assert "[REMOTE]" in output


def test_end_message():
    """Test that end message includes instructions."""
    formatter = DryRunFormatter()
    jobs = [SyncJob(file_path="test.txt", action=SyncAction.COPY_LEFT_TO_RIGHT)]

    output = formatter.format_dry_run_output(jobs)

    assert "END DRY RUN" in output
    assert "dry_run: false" in output
