"""Main entry point for the sync engine."""

import argparse
import getpass
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from remote_office_sync.config_loader import ConfigError, load_config, load_config_from_env
from remote_office_sync.dry_run_formatter import DryRunFormatter
from remote_office_sync.email_notifications import (
    ConflictAlert,
    EmailConfig,
    EmailNotifier,
    ErrorAlert,
)
from remote_office_sync.file_ops import FileOps, FileOpsError
from remote_office_sync.filesystem_utils import detect_mtime_precision
from remote_office_sync.logging_setup import get_logger, setup_logging
from remote_office_sync.scanner import FileMetadata, Scanner
from remote_office_sync.soft_delete import SoftDeleteManager
from remote_office_sync.state_db import StateDB
from remote_office_sync.sync_logic import SyncAction, SyncEngine

logger = get_logger()


class SyncRunner:
    """Orchestrates the sync process."""

    def __init__(self, config_path: str):
        """Initialize sync runner.

        Args:
            config_path: Path to config.yaml file
        """
        self.config = load_config(config_path)
        setup_logging(
            self.config.log_file_path,
            self.config.log_level,
            max_bytes=self.config.log_max_size_mb * 1024 * 1024,
            backup_count=self.config.log_backup_count,
            rotation_enabled=self.config.log_rotation_enabled,
        )

        # Detect filesystem mtime precision difference
        logger.info("Detecting filesystem modification time precision...")
        self.mtime_tolerance = detect_mtime_precision(self.config.left_root, self.config.right_root)

        self.scanner = Scanner(
            ignore_extensions=self.config.ignore_extensions,
            ignore_filenames_prefix=self.config.ignore_filenames_prefix,
            ignore_filenames_exact=self.config.ignore_filenames_exact,
            ignore_directories=self.config.ignore_directories,
        )
        self.state_db = StateDB("sync_state.db")
        self.file_ops = FileOps(soft_delete_root=".deleted")
        self.soft_delete_mgr = SoftDeleteManager(
            soft_delete_root=".deleted",
            max_size_bytes=self.config.soft_delete_max_size_bytes,
        )

        # Setup email notifier
        email_config = EmailConfig(
            enabled=self.config.email_enabled,
            smtp_host=self.config.email_smtp_host,
            smtp_port=self.config.email_smtp_port,
            username=self.config.email_username,
            password=self.config.email_password,
            from_addr=self.config.email_from,
            to_addrs=self.config.email_to,
        )
        self.email_notifier = EmailNotifier(email_config)

        # Get current username for conflict tracking
        try:
            self.username = getpass.getuser()
        except Exception:
            self.username = "unknown"

        self.conflict_alerts: List[ConflictAlert] = []
        self.error_alerts: List[ErrorAlert] = []
        self.content_conflicts_detected = False

    def run(self) -> bool:
        """Execute the sync process.

        Returns:
            True if sync completed successfully
        """
        try:
            logger.info("Starting sync engine")
            self.content_conflicts_detected = False
            self._run_sync_cycle()

            # If content conflicts were detected, run sync again to sync conflict files
            # Note: case conflicts don't need a second sync as they're already resolved
            if self.content_conflicts_detected:
                logger.info(
                    "Content conflicts detected - running second sync to sync " "conflict files"
                )
                print("\nRunning second sync to sync conflict files...\n")
                self.content_conflicts_detected = False
                self._run_sync_cycle()

            return True
        except Exception as e:
            logger.exception(f"Sync engine failed: {e}")
            return False

    def _run_sync_cycle(self) -> bool:
        """Execute one sync cycle.

        Returns:
            True if conflicts were detected
        """
        # Clear alerts from previous cycle
        self.conflict_alerts.clear()
        self.error_alerts.clear()

        # Load previous state
        logger.info("Loading previous sync state")
        previous_state = self.state_db.load_state()

        # Scan directories
        logger.info(f"Scanning left directory: {self.config.left_root}")
        left_scan = self.scanner.scan_directory(self.config.left_root)

        logger.info(f"Scanning right directory: {self.config.right_root}")
        right_scan = self.scanner.scan_directory(self.config.right_root)

        # Merge scans
        current_state = self.scanner.merge_scans(left_scan, right_scan)

        # Generate sync jobs
        logger.info("Generating sync jobs")
        sync_engine = SyncEngine(self.config, previous_state, current_state, self.mtime_tolerance)
        jobs = sync_engine.generate_sync_jobs()

        # Check for dry run mode
        if self.config.dry_run:
            logger.info("DRY RUN MODE: Showing preview without making changes")
            formatter = DryRunFormatter(left_name="LEFT", right_name="RIGHT")
            output = formatter.format_dry_run_output(jobs)
            print("\n" + output + "\n")
            return False  # No conflicts in dry run

        # Execute sync jobs
        logger.info(f"Executing {len(jobs)} sync jobs")

        # DEBUG: Check file state BEFORE any job execution
        def _safe_preview(path: Path) -> str:
            try:
                raw = path.read_bytes()[:50]
                return (
                    raw.decode(errors="replace").encode("unicode_escape").decode("ascii", "replace")
                )
            except (OSError, IOError):
                return "<unreadable>"

        test_left = Path(self.config.left_root) / "CaseTest.txt"
        test_right = Path(self.config.right_root) / "casetest.txt"
        if test_left.exists():
            logger.debug(f"BEFORE jobs: Left file content: {_safe_preview(test_left)}")
        if test_right.exists():
            logger.debug(f"BEFORE jobs: Right file content: {_safe_preview(test_right)}")

        executed = 0
        failed = 0

        for job in jobs:
            try:
                if self._execute_job(job):
                    executed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Job failed: {job.file_path}: {e}")
                self.error_alerts.append(
                    ErrorAlert(
                        error_message=str(e),
                        error_type="Job Execution Error",
                        affected_file=job.file_path,
                    )
                )
                failed += 1

        # Clean up state: merge case variant entries back to their canonical form
        # After case conflicts are resolved, remove variant entries from state
        self._cleanup_case_variants(current_state)

        # Rescan directories to get the actual state after sync operations
        logger.info("Rescanning directories after sync to capture actual state")
        scanner = Scanner()
        left_scan = scanner.scan_directory(self.config.left_root)
        right_scan = scanner.scan_directory(self.config.right_root)
        final_state = scanner.merge_scans(left_scan, right_scan)

        # Save the actual post-sync state
        logger.info("Saving sync state")
        self.state_db.save_state(final_state)

        # Send notifications
        if self.conflict_alerts:
            self.email_notifier.send_conflict_email(self.conflict_alerts)

        if self.error_alerts:
            self.email_notifier.send_error_email(self.error_alerts)

        # Print summary
        logger.info(f"Sync completed: {executed} jobs executed, {failed} failed")
        print(f"\n{'='*50}")
        print("Sync Summary")
        print(f"{'='*50}")
        print(f"Total files processed: {len(current_state)}")
        print(f"Sync jobs executed: {executed}")
        print(f"Jobs failed: {failed}")
        print(f"Conflicts detected: {len(self.conflict_alerts)}")
        print(f"Errors: {len(self.error_alerts)}")
        size_mb = self.soft_delete_mgr.get_soft_delete_size() / (1024 * 1024)
        print(f"Soft delete directory size: {size_mb:.2f} MB")
        print(f"{'='*50}\n")

        # Return whether conflicts were detected
        return len(self.conflict_alerts) > 0

    def _execute_job(self, job) -> bool:
        """Execute a single sync job.

        Args:
            job: SyncJob to execute

        Returns:
            True if successful
        """
        left_path = Path(self.config.left_root) / job.file_path
        right_path = Path(self.config.right_root) / job.file_path

        try:
            if job.action == SyncAction.COPY_LEFT_TO_RIGHT:
                self.file_ops.ensure_directory(str(right_path.parent))
                self.file_ops.copy_file(str(left_path), str(right_path))
                logger.info(f"[COPY_LEFT_TO_RIGHT] {job.file_path}")

            elif job.action == SyncAction.COPY_RIGHT_TO_LEFT:
                self.file_ops.ensure_directory(str(left_path.parent))
                self.file_ops.copy_file(str(right_path), str(left_path))
                logger.info(f"[COPY_RIGHT_TO_LEFT] {job.file_path}")

            elif job.action == SyncAction.DELETE_LEFT:
                self.file_ops.delete_file(str(left_path), soft=False)
                logger.info(f"[DELETE_LEFT] {job.file_path}")

            elif job.action == SyncAction.DELETE_RIGHT:
                self.file_ops.delete_file(str(right_path), soft=False)
                logger.info(f"[DELETE_RIGHT] {job.file_path}")

            elif job.action == SyncAction.SOFT_DELETE_LEFT:
                self.file_ops.delete_file(
                    str(left_path),
                    soft=True,
                    max_size_bytes=self.config.soft_delete_max_size_bytes,
                )
                logger.info(f"[SOFT_DELETE_LEFT] {job.file_path}")

            elif job.action == SyncAction.SOFT_DELETE_RIGHT:
                self.file_ops.delete_file(
                    str(right_path),
                    soft=True,
                    max_size_bytes=self.config.soft_delete_max_size_bytes,
                )
                logger.info(f"[SOFT_DELETE_RIGHT] {job.file_path}")

            elif job.action == SyncAction.CLASH_CREATE:
                # Create clash file from the older version, keep newer as main
                current = self.state_db.load_state().get(job.file_path)
                if current and current.exists_left and current.exists_right:
                    left_mtime = current.mtime_left or 0
                    right_mtime = current.mtime_right or 0

                    # Determine which is older and create conflict file from it
                    if left_mtime > right_mtime:
                        # Left is newer - create conflict from right (older)
                        conflict_file = self.file_ops.create_clash_file(
                            str(right_path), username=self.username
                        )
                        self.file_ops.copy_file(str(left_path), str(right_path))
                        logger.info(
                            f"[CONFLICT] {job.file_path}: "
                            f"older version saved as {conflict_file}"
                        )
                    else:
                        # Right is newer - create conflict from left (older)
                        conflict_file = self.file_ops.create_clash_file(
                            str(left_path), username=self.username
                        )
                        self.file_ops.copy_file(str(right_path), str(left_path))
                        logger.info(
                            f"[CONFLICT] {job.file_path}: "
                            f"older version saved as {conflict_file}"
                        )

                    # Record conflict alert
                    self.conflict_alerts.append(
                        ConflictAlert(
                            file_path=job.file_path,
                            conflict_type=job.details or "unknown",
                            left_mtime=current.mtime_left,
                            right_mtime=current.mtime_right,
                            left_size=current.size_left,
                            right_size=current.size_right,
                        )
                    )
                    # Mark that we have a content conflict needing a second sync
                    self.content_conflicts_detected = True

            elif job.action == SyncAction.CASE_CONFLICT:
                # Handle case conflict: different cases on each side
                # Strategy: Keep the NEWER file (by mtime) on both sides with its case
                #           Create conflict file from the OLDER file
                # job.file_path = left case, job.src_path = right case
                left_case_path = Path(self.config.left_root) / job.file_path
                right_case_path = Path(self.config.right_root) / job.src_path

                # DEBUG: Check file states at the START of handler
                logger.debug("=== CASE_CONFLICT handler START ===")
                logger.debug(f"Left path: {left_case_path}, exists: {left_case_path.exists()}")
                logger.debug(f"Right path: {right_case_path}, exists: {right_case_path.exists()}")

                def _force_case_rename(existing: Path, desired: Path) -> None:
                    """Ensure filename casing matches desired by using a temp hop."""
                    try:
                        if not existing.exists():
                            return
                        if existing.name == desired.name:
                            return
                        desired.parent.mkdir(parents=True, exist_ok=True)
                        # On case-insensitive FS a direct rename may no-op; hop through a temp.
                        temp = desired.with_name(
                            f"{desired.stem}.case_tmp.{uuid.uuid4().hex}{desired.suffix}"
                        )
                        existing.rename(temp)
                        temp.rename(desired)
                        logger.debug(f"Renamed for casing: {existing} -> {desired}")
                    except (OSError, IOError) as exc:
                        logger.warning(f"Failed to normalize casing {existing} -> {desired}: {exc}")

                def _safe_content_preview(path: Path) -> str:
                    try:
                        raw = path.read_bytes()[:50]
                        return (
                            raw.decode(errors="replace")
                            .encode("unicode_escape")
                            .decode("ascii", "replace")
                        )
                    except (OSError, IOError):
                        return "<unreadable>"

                if left_case_path.exists():
                    logger.debug(
                        f"Left content (first 50): {_safe_content_preview(left_case_path)}"
                    )
                if right_case_path.exists():
                    logger.debug(
                        f"Right content (first 50): {_safe_content_preview(right_case_path)}"
                    )

                try:
                    payload = getattr(job, "payload", None) or {}

                    # Prefer captured mtimes/content from job creation to avoid later mutations
                    left_mtime = payload.get("left_mtime")
                    right_mtime = payload.get("right_mtime")
                    left_bytes = payload.get("left_bytes")
                    right_bytes = payload.get("right_bytes")

                    if left_mtime is None:
                        left_mtime = (
                            left_case_path.stat().st_mtime if left_case_path.exists() else 0
                        )
                    if right_mtime is None:
                        right_mtime = (
                            right_case_path.stat().st_mtime if right_case_path.exists() else 0
                        )

                    logger.debug(
                        f"CASE_CONFLICT snapshot mtimes - left: {left_mtime}, right: {right_mtime}"
                    )

                    def _resolve_bytes(path: Path, cached: Optional[bytes]) -> Optional[bytes]:
                        if cached is not None:
                            return cached
                        if not path.exists():
                            return None
                        try:
                            return path.read_bytes()
                        except (OSError, IOError) as exc:
                            logger.error(f"Failed to read bytes from {path}: {exc}")
                            return None

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                    # Name conflict file using the older variant's casing by default (updated below)
                    conflict_stem = left_case_path.stem
                    conflict_suffix = left_case_path.suffix

                    # Tie-breaker: if mtimes equal, prefer the side that changed casing.
                    winner_is_left = left_mtime > right_mtime
                    if left_mtime == right_mtime:
                        # On equal mtimes, keep the LEFT variant and conflict the RIGHT variant.
                        winner_is_left = True

                    log_message = ""
                    if winner_is_left:
                        # Left is newer - conflict file from right (older)
                        conflict_stem = right_case_path.stem
                        conflict_suffix = right_case_path.suffix
                        older_bytes = _resolve_bytes(right_case_path, right_bytes)
                        if older_bytes is None:
                            raise FileOpsError(
                                f"Missing older content for case conflict "
                                f"(right): {right_case_path}"
                            )

                        older_mtime = right_mtime

                        right_unified = Path(self.config.right_root) / job.file_path
                        self.file_ops.copy_file(str(left_case_path), str(right_unified))
                        # Normalize case on right to match canonical left casing
                        _force_case_rename(right_case_path, right_unified)

                        log_message = (
                            f"[CASE_CONFLICT] {job.file_path}: "
                            "left newer (kept), conflict from right"
                        )
                    else:
                        # Right is newer - conflict file from left (older)
                        conflict_stem = left_case_path.stem
                        conflict_suffix = left_case_path.suffix
                        older_bytes = _resolve_bytes(left_case_path, left_bytes)
                        if older_bytes is None:
                            raise FileOpsError(
                                f"Missing older content for case conflict (left): {left_case_path}"
                            )

                        older_mtime = left_mtime

                        left_unified = (
                            Path(self.config.left_root) / job.src_path
                        )  # Use right's case
                        right_unified = (
                            Path(self.config.right_root) / job.src_path
                        )  # Use right's case
                        self.file_ops.copy_file(str(right_case_path), str(left_unified))
                        if str(right_case_path) != str(right_unified):
                            self.file_ops.copy_file(str(right_case_path), str(right_unified))
                        # Normalize case on both sides to match the newer (right) casing
                        _force_case_rename(left_case_path, left_unified)
                        _force_case_rename(right_case_path, right_unified)

                        log_message = (
                            f"[CASE_CONFLICT] {job.src_path}: "
                            "right newer (kept), conflict from left"
                        )

                    conflict_name = (
                        f"{conflict_stem}.CONFLICT.{self.username}.{timestamp}{conflict_suffix}"
                    )
                    left_conflict = Path(self.config.left_root) / conflict_name
                    right_conflict = Path(self.config.right_root) / conflict_name
                    left_conflict.parent.mkdir(parents=True, exist_ok=True)
                    right_conflict.parent.mkdir(parents=True, exist_ok=True)

                    # Write conflict content from the older variant
                    left_conflict.write_bytes(older_bytes)
                    right_conflict.write_bytes(older_bytes)
                    if older_mtime:
                        os.utime(left_conflict, (older_mtime, older_mtime))
                        os.utime(right_conflict, (older_mtime, older_mtime))

                    if log_message:
                        logger.info(f"{log_message} ({left_conflict.name})")

                    # Record conflict alert
                    self.conflict_alerts.append(
                        ConflictAlert(
                            file_path=job.file_path,
                            conflict_type="case_conflict",
                            left_mtime=left_mtime,
                            right_mtime=right_mtime,
                            left_size=(
                                left_case_path.stat().st_size if left_case_path.exists() else None
                            ),
                            right_size=(
                                right_case_path.stat().st_size if right_case_path.exists() else None
                            ),
                        )
                    )
                    self.content_conflicts_detected = (
                        False  # Don't need second sync for case conflicts
                    )

                except (OSError, IOError, FileOpsError) as e:
                    logger.error(f"Failed to handle case conflict for {job.file_path}: {e}")
                    return False

            elif job.action == SyncAction.RENAME_CONFLICT:
                # Handle rename conflict: right_new exists on right, left_new on left
                # For case conflicts: keep main case file, create conflict from variant
                # Expected result: main file on both sides + conflict file on both sides

                left_main_path = Path(self.config.left_root) / job.src_path
                right_main_path = Path(self.config.right_root) / job.src_path
                right_variant_path = Path(self.config.right_root) / job.file_path

                # Step 1: Create conflict file from the variant (right side has it)
                if right_variant_path.exists():
                    # Create conflict file on right from variant
                    right_conflict_file = self.file_ops.create_clash_file(
                        str(right_variant_path), username=self.username
                    )
                    logger.info(
                        f"[RENAME_CONFLICT] Created conflict file on right: "
                        f"{right_conflict_file}"
                    )
                    # Copy conflict file to left (preserve directory structure)
                    right_conflict_relative = Path(right_conflict_file).relative_to(
                        self.config.right_root
                    )
                    left_conflict_file = Path(self.config.left_root) / right_conflict_relative
                    self.file_ops.ensure_directory(str(left_conflict_file.parent))
                    self.file_ops.copy_file(str(right_conflict_file), str(left_conflict_file))
                    logger.info(
                        f"[RENAME_CONFLICT] Copied conflict file to left: " f"{left_conflict_file}"
                    )
                    # Delete the variant on right (we have it in conflict file now)
                    self.file_ops.delete_file(str(right_variant_path), soft=False)
                    logger.info(f"[RENAME_CONFLICT] Deleted variant on right: {job.file_path}")

                # Step 2: Ensure main case exists on both sides
                if left_main_path.exists() and not right_main_path.exists():
                    # Copy main from left to right
                    self.file_ops.copy_file(str(left_main_path), str(right_main_path))
                    logger.info(
                        f"[RENAME_CONFLICT] Copied main case from left to right: " f"{job.src_path}"
                    )

                # Record conflict alert
                current = self.state_db.load_state().get(job.file_path)
                if current:
                    self.conflict_alerts.append(
                        ConflictAlert(
                            file_path=job.file_path,
                            conflict_type="Rename Conflict",
                            left_mtime=current.mtime_left,
                            right_mtime=current.mtime_right,
                            left_size=current.size_left,
                            right_size=current.size_right,
                        )
                    )

            elif job.action == SyncAction.RENAME_LEFT:
                # Rename file on left side from job.file_path to job.dst_path
                old_left_path = Path(self.config.left_root) / job.file_path
                new_left_path = Path(self.config.left_root) / job.dst_path
                self.file_ops.ensure_directory(str(new_left_path.parent))
                self.file_ops.rename_file(str(old_left_path), str(new_left_path))
                logger.info(f"[RENAME_LEFT] {job.file_path} -> {job.dst_path}")

            elif job.action == SyncAction.RENAME_RIGHT:
                # Rename file on right side from job.file_path to job.dst_path
                old_right_path = Path(self.config.right_root) / job.file_path
                new_right_path = Path(self.config.right_root) / job.dst_path
                self.file_ops.ensure_directory(str(new_right_path.parent))
                self.file_ops.rename_file(str(old_right_path), str(new_right_path))
                logger.info(f"[RENAME_RIGHT] {job.file_path} -> {job.dst_path}")

            elif job.action == SyncAction.CREATE_DIR_LEFT:
                # Create empty directory on left
                dir_path = Path(self.config.left_root) / job.file_path
                self.file_ops.ensure_directory(str(dir_path))
                logger.info(f"[CREATE_DIR_LEFT] Created directory: {job.file_path}")

            elif job.action == SyncAction.CREATE_DIR_RIGHT:
                # Create empty directory on right
                dir_path = Path(self.config.right_root) / job.file_path
                self.file_ops.ensure_directory(str(dir_path))
                logger.info(f"[CREATE_DIR_RIGHT] Created directory: {job.file_path}")

            elif job.action == SyncAction.DELETE_DIR_LEFT:
                # Delete empty directory from left
                dir_path = Path(self.config.left_root) / job.file_path
                if dir_path.exists() and dir_path.is_dir():
                    # Only delete if still empty
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        logger.info(f"[DELETE_DIR_LEFT] Deleted empty directory: {job.file_path}")
                    else:
                        logger.warning(
                            f"[DELETE_DIR_LEFT] Skipping {job.file_path}: " f"directory not empty"
                        )

            elif job.action == SyncAction.DELETE_DIR_RIGHT:
                # Delete empty directory from right
                dir_path = Path(self.config.right_root) / job.file_path
                if dir_path.exists() and dir_path.is_dir():
                    # Only delete if still empty
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        logger.info(f"[DELETE_DIR_RIGHT] Deleted empty directory: {job.file_path}")
                    else:
                        logger.warning(
                            f"[DELETE_DIR_RIGHT] Skipping {job.file_path}: " f"directory not empty"
                        )

            elif job.action == SyncAction.NOOP:
                logger.info(f"[NOOP] {job.file_path}: {job.details}")

            return True
        except FileOpsError as e:
            logger.error(f"File operation failed for {job.file_path}: {e}")
            return False

    def _cleanup_case_variants(self, current_state: Dict[str, FileMetadata]) -> None:
        """Remove case variant entries from state after conflicts are resolved.

        After a case conflict is resolved, we have two entries in current_state:
        one for the main case and one for the variant case. This removes the
        variant entries so the next sync cycle doesn't detect them again.

        Args:
            current_state: Dictionary of file metadata to clean up
        """
        # Group paths by lowercase version
        paths_by_lower = {}
        for path in list(current_state.keys()):
            lower = path.lower()
            if lower not in paths_by_lower:
                paths_by_lower[lower] = []
            paths_by_lower[lower].append(path)

        # DON'T remove variant entries - we need to preserve actual case on both sides
        # for proper case change detection in future syncs
        # for lower, paths in paths_by_lower.items():
        #     if len(paths) > 1:
        #         # Multiple case variants exist - keep the one that exists on both sides
        #         # or the main one, and remove the variant
        #         main_entry = None
        #         variant_entries = []
        #
        #         for path in paths:
        #             meta = current_state[path]
        #             if meta.exists_left and meta.exists_right:
        #                 main_entry = path
        #             else:
        #                 variant_entries.append(path)
        #
        #         # Remove variant entries from state
        #         for variant in variant_entries:
        #             del current_state[variant]
        #             logger.debug(
        #                 f"Removed case variant from state: {variant} "
        #                 f"(kept main entry: {main_entry})"
        #             )


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Remote Office File Sync - Bidirectional sync engine"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config.yaml file",
    )
    parser.add_argument(
        "--use-env",
        action="store_true",
        help="Load config from SYNC_CONFIG environment variable",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Disable dry run mode and perform actual file synchronization",
    )

    args = parser.parse_args()

    try:
        # Determine config source
        if args.use_env:
            logger.info("Loading config from environment variable")
            try:
                runner = SyncRunner.__new__(SyncRunner)
                runner.config = load_config_from_env()

                # Detect filesystem mtime precision difference
                logger.info("Detecting filesystem modification time precision...")
                runner.mtime_tolerance = detect_mtime_precision(
                    runner.config.left_root, runner.config.right_root
                )

                runner.scanner = Scanner(
                    ignore_extensions=runner.config.ignore_extensions,
                    ignore_filenames_prefix=runner.config.ignore_filenames_prefix,
                    ignore_filenames_exact=runner.config.ignore_filenames_exact,
                    ignore_directories=runner.config.ignore_directories,
                )
                runner.state_db = StateDB("sync_state.db")
                runner.file_ops = FileOps(soft_delete_root=".deleted")
                runner.soft_delete_mgr = SoftDeleteManager(
                    soft_delete_root=".deleted",
                    max_size_bytes=runner.config.soft_delete_max_size_bytes,
                )
                email_config = EmailConfig(
                    enabled=runner.config.email_enabled,
                    smtp_host=runner.config.email_smtp_host,
                    smtp_port=runner.config.email_smtp_port,
                    username=runner.config.email_username,
                    password=runner.config.email_password,
                    from_addr=runner.config.email_from,
                    to_addrs=runner.config.email_to,
                )
                runner.email_notifier = EmailNotifier(email_config)
                runner.conflict_alerts = []
                runner.error_alerts = []
            except ConfigError as e:
                logger.error(f"Config error: {e}")
                return 1
        elif args.config:
            runner = SyncRunner(args.config)
        else:
            # Try default config path
            default_config = "config.yaml"
            if Path(default_config).exists():
                runner = SyncRunner(default_config)
            else:
                parser.print_help()
                logger.error(
                    "No config file specified. Use --config or --use-env, "
                    "or place config.yaml in current directory"
                )
                return 1

        # Override dry_run if --no-dry-run flag is provided
        if args.no_dry_run:
            logger.info("--no-dry-run flag provided: disabling dry run mode")
            runner.config._config["dry_run"] = False

        # Run sync
        success = runner.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
