"""Main entry point for the sync engine."""

import argparse
import sys
from pathlib import Path
from typing import List

from remote_office_sync.config_loader import ConfigError, load_config, load_config_from_env
from remote_office_sync.email_notifications import (
    ConflictAlert,
    EmailConfig,
    EmailNotifier,
    ErrorAlert,
)
from remote_office_sync.file_ops import FileOps, FileOpsError
from remote_office_sync.logging_setup import get_logger, setup_logging
from remote_office_sync.scanner import Scanner
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
        setup_logging(self.config.log_file_path, self.config.log_level)

        self.scanner = Scanner(
            ignore_extensions=self.config.ignore_extensions,
            ignore_filenames_prefix=self.config.ignore_filenames_prefix,
            ignore_filenames_exact=self.config.ignore_filenames_exact,
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

        self.conflict_alerts: List[ConflictAlert] = []
        self.error_alerts: List[ErrorAlert] = []

    def run(self) -> bool:
        """Execute the sync process.

        Returns:
            True if sync completed successfully
        """
        try:
            logger.info("Starting sync engine")

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
            sync_engine = SyncEngine(self.config, previous_state, current_state)
            jobs = sync_engine.generate_sync_jobs()

            # Execute sync jobs
            logger.info(f"Executing {len(jobs)} sync jobs")
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

            # Save updated state
            logger.info("Saving sync state")
            self.state_db.save_state(current_state)

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

            return failed == 0
        except Exception as e:
            logger.exception(f"Sync engine failed: {e}")
            return False

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
                        conflict_file = self.file_ops.create_clash_file(str(right_path))
                        self.file_ops.copy_file(str(left_path), str(right_path))
                        logger.info(
                            f"[CONFLICT] {job.file_path}: "
                            f"older version saved as {conflict_file}"
                        )
                    else:
                        # Right is newer - create conflict from left (older)
                        conflict_file = self.file_ops.create_clash_file(str(left_path))
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

            elif job.action == SyncAction.NOOP:
                logger.info(f"[NOOP] {job.file_path}: {job.details}")

            return True
        except FileOpsError as e:
            logger.error(f"File operation failed for {job.file_path}: {e}")
            return False


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

    args = parser.parse_args()

    try:
        # Determine config source
        if args.use_env:
            logger.info("Loading config from environment variable")
            try:
                runner = SyncRunner.__new__(SyncRunner)
                runner.config = load_config_from_env()
                runner.scanner = Scanner(
                    ignore_extensions=runner.config.ignore_extensions,
                    ignore_filenames_prefix=runner.config.ignore_filenames_prefix,
                    ignore_filenames_exact=runner.config.ignore_filenames_exact,
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
