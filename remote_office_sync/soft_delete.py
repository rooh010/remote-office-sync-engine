"""Soft delete management for deleted files."""

from pathlib import Path
from typing import List, Tuple

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


class SoftDeleteManager:
    """Manages soft-deleted files."""

    def __init__(self, soft_delete_root: str = ".deleted", max_size_bytes: int = 20 * 1024 * 1024):
        """Initialize soft delete manager.

        Args:
            soft_delete_root: Root directory for soft-deleted files
            max_size_bytes: Maximum file size for soft delete (default 20 MB)
        """
        self.soft_delete_root = soft_delete_root
        self.max_size_bytes = max_size_bytes

    def should_soft_delete(self, file_size: int) -> bool:
        """Check if file should be soft deleted based on size.

        Args:
            file_size: Size of file in bytes

        Returns:
            True if file should be soft deleted
        """
        return file_size <= self.max_size_bytes

    def get_soft_delete_dir(self) -> Path:
        """Get soft delete directory path.

        Returns:
            Path to soft delete directory
        """
        return Path(self.soft_delete_root)

    def list_deleted_files(self) -> List[Tuple[str, int]]:
        """List all soft-deleted files.

        Returns:
            List of (filename, size) tuples
        """
        soft_delete_path = self.get_soft_delete_dir()

        if not soft_delete_path.exists():
            return []

        deleted_files = []

        try:
            for file_path in soft_delete_path.rglob("*"):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    deleted_files.append((str(file_path.relative_to(soft_delete_path)), size))

            logger.info(f"Found {len(deleted_files)} soft-deleted files")
        except OSError as e:
            logger.warning(f"Error listing soft-deleted files: {e}")

        return deleted_files

    def get_soft_delete_size(self) -> int:
        """Get total size of soft-deleted files.

        Returns:
            Total size in bytes
        """
        total = 0

        try:
            for _, size in self.list_deleted_files():
                total += size
        except OSError as e:
            logger.warning(f"Error calculating soft delete size: {e}")

        return total

    def purge_old_deleted_files(self, days_old: int = 30) -> int:
        """Remove soft-deleted files older than specified days.

        Args:
            days_old: Age threshold in days

        Returns:
            Number of files purged
        """
        import time

        soft_delete_path = self.get_soft_delete_dir()

        if not soft_delete_path.exists():
            return 0

        purged = 0
        now = time.time()
        threshold = now - (days_old * 24 * 3600)

        try:
            for file_path in soft_delete_path.rglob("*"):
                if file_path.is_file():
                    mtime = file_path.stat().st_mtime

                    if mtime < threshold:
                        file_path.unlink()
                        purged += 1
                        logger.info(f"Purged old deleted file: {file_path}")

            logger.info(f"Purged {purged} files older than {days_old} days")
        except (OSError, IOError) as e:
            logger.error(f"Error purging old deleted files: {e}")

        return purged

    def clear_all_deleted(self) -> None:
        """Clear all soft-deleted files."""
        soft_delete_path = self.get_soft_delete_dir()

        if not soft_delete_path.exists():
            return

        try:
            import shutil

            shutil.rmtree(soft_delete_path)
            logger.info("Cleared all soft-deleted files")
        except (OSError, IOError) as e:
            logger.error(f"Error clearing soft-deleted files: {e}")
