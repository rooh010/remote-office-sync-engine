"""Dry run output formatter with visual diagrams."""

from typing import List

from remote_office_sync.logging_setup import get_logger
from remote_office_sync.sync_logic import SyncAction, SyncJob

logger = get_logger()


class DryRunFormatter:
    """Formats dry run output with visual diagrams."""

    # Action symbols and descriptions
    ACTION_SYMBOLS = {
        SyncAction.COPY_LEFT_TO_RIGHT: "->",
        SyncAction.COPY_RIGHT_TO_LEFT: "<-",
        SyncAction.DELETE_LEFT: "[X]",
        SyncAction.DELETE_RIGHT: "[X]",
        SyncAction.SOFT_DELETE_LEFT: "[~]",
        SyncAction.SOFT_DELETE_RIGHT: "[~]",
        SyncAction.CLASH_CREATE: "[!]",
        SyncAction.RENAME_LEFT: "[R]",
        SyncAction.RENAME_RIGHT: "[R]",
        SyncAction.RENAME_CONFLICT: "[R!]",
        SyncAction.CREATE_DIR_LEFT: "[+D]",
        SyncAction.CREATE_DIR_RIGHT: "[+D]",
        SyncAction.DELETE_DIR_LEFT: "[-D]",
        SyncAction.DELETE_DIR_RIGHT: "[-D]",
    }

    ACTION_DESCRIPTIONS = {
        SyncAction.COPY_LEFT_TO_RIGHT: "Copy LEFT -> RIGHT",
        SyncAction.COPY_RIGHT_TO_LEFT: "Copy RIGHT -> LEFT",
        SyncAction.DELETE_LEFT: "Delete from LEFT",
        SyncAction.DELETE_RIGHT: "Delete from RIGHT",
        SyncAction.SOFT_DELETE_LEFT: "Soft delete from LEFT",
        SyncAction.SOFT_DELETE_RIGHT: "Soft delete from RIGHT",
        SyncAction.CLASH_CREATE: "Conflict - preserve both versions",
        SyncAction.RENAME_LEFT: "Rename on LEFT",
        SyncAction.RENAME_RIGHT: "Rename on RIGHT",
        SyncAction.RENAME_CONFLICT: "Rename conflict - resolve",
        SyncAction.CREATE_DIR_LEFT: "Create directory on LEFT",
        SyncAction.CREATE_DIR_RIGHT: "Create directory on RIGHT",
        SyncAction.DELETE_DIR_LEFT: "Delete directory from LEFT",
        SyncAction.DELETE_DIR_RIGHT: "Delete directory from RIGHT",
    }

    def __init__(self, left_name: str = "LEFT", right_name: str = "RIGHT"):
        """Initialize formatter.

        Args:
            left_name: Display name for left side
            right_name: Display name for right side
        """
        self.left_name = left_name
        self.right_name = right_name

    def format_dry_run_output(self, jobs: List[SyncJob]) -> str:
        """Format dry run output with visual diagrams.

        Args:
            jobs: List of sync jobs that would be executed

        Returns:
            Formatted output string
        """
        if not jobs:
            return self._format_no_changes()

        # Group jobs by action type
        grouped = self._group_jobs_by_action(jobs)

        output = []
        output.append("=" * 80)
        output.append("DRY RUN MODE - NO CHANGES WILL BE MADE")
        output.append("=" * 80)
        output.append("")
        output.append(f"The following {len(jobs)} operations would be performed:\n")

        # Show summary by action type
        output.append("Summary by Action:")
        output.append("-" * 80)
        for action, action_jobs in grouped.items():
            symbol = self.ACTION_SYMBOLS.get(action, "?")
            desc = self.ACTION_DESCRIPTIONS.get(action, str(action))
            output.append(f"  {symbol} {desc}: {len(action_jobs)} files")
        output.append("")

        # Show detailed visual diagrams
        output.append("Detailed Changes:")
        output.append("-" * 80)

        for action, action_jobs in grouped.items():
            if not action_jobs:
                continue

            output.append(f"\n{self.ACTION_DESCRIPTIONS.get(action, str(action))}:")
            output.append("")

            for job in action_jobs:
                output.append(self._format_job_diagram(job))

        output.append("")
        output.append("=" * 80)
        output.append("END DRY RUN - To perform these changes, set dry_run: false in config")
        output.append("=" * 80)

        return "\n".join(output)

    def _group_jobs_by_action(self, jobs: List[SyncJob]) -> dict:
        """Group jobs by action type.

        Args:
            jobs: List of sync jobs

        Returns:
            Dictionary mapping action to list of jobs
        """
        grouped = {}
        for job in jobs:
            if job.action not in grouped:
                grouped[job.action] = []
            grouped[job.action].append(job)
        return grouped

    def _format_job_diagram(self, job: SyncJob) -> str:
        """Format a single job as a visual diagram.

        Args:
            job: Sync job to format

        Returns:
            Formatted diagram string
        """
        symbol = self.ACTION_SYMBOLS.get(job.action, "?")
        filename = job.file_path

        if job.action == SyncAction.COPY_LEFT_TO_RIGHT:
            return f"  [{self.left_name}] {filename} {symbol} [{self.right_name}]"

        elif job.action == SyncAction.COPY_RIGHT_TO_LEFT:
            return f"  [{self.left_name}] {symbol} {filename} [{self.right_name}]"

        elif job.action == SyncAction.DELETE_LEFT:
            return f"  [{self.left_name}] {filename} {symbol} (delete)"

        elif job.action == SyncAction.DELETE_RIGHT:
            return f"  [{self.right_name}] {filename} {symbol} (delete)"

        elif job.action == SyncAction.SOFT_DELETE_LEFT:
            return f"  [{self.left_name}] {filename} {symbol} (move to .deleted/)"

        elif job.action == SyncAction.SOFT_DELETE_RIGHT:
            return f"  [{self.right_name}] {filename} {symbol} (move to .deleted/)"

        elif job.action == SyncAction.CLASH_CREATE:
            return (
                f"  [{self.left_name}] {filename} {symbol} "
                f"[{self.right_name}] (create conflict file)"
            )

        elif job.action == SyncAction.RENAME_CONFLICT:
            return f"  [{self.left_name}] {filename} {symbol} [{self.right_name}] (resolve rename)"

        elif job.action == SyncAction.RENAME_LEFT:
            return f"  [{self.left_name}] {filename} {symbol} (rename)"

        elif job.action == SyncAction.RENAME_RIGHT:
            return f"  [{self.right_name}] {filename} {symbol} (rename)"

        elif job.action == SyncAction.CREATE_DIR_LEFT:
            return f"  [{self.left_name}] {filename} {symbol} (create directory)"

        elif job.action == SyncAction.CREATE_DIR_RIGHT:
            return f"  [{self.right_name}] {filename} {symbol} (create directory)"

        elif job.action == SyncAction.DELETE_DIR_LEFT:
            return f"  [{self.left_name}] {filename} {symbol} (delete directory)"

        elif job.action == SyncAction.DELETE_DIR_RIGHT:
            return f"  [{self.right_name}] {filename} {symbol} (delete directory)"

        else:
            return f"  {filename} ({job.action})"

    def _format_no_changes(self) -> str:
        """Format output when no changes are needed.

        Returns:
            Formatted output string
        """
        output = []
        output.append("=" * 80)
        output.append("DRY RUN MODE - NO CHANGES WILL BE MADE")
        output.append("=" * 80)
        output.append("")
        output.append("[OK] No synchronization needed - all files are already in sync!")
        output.append("")
        output.append("=" * 80)
        return "\n".join(output)
