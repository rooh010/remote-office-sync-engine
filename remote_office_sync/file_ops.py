"""File operations layer for sync actions."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


class FileOpsError(Exception):
    """Raised when file operation fails."""

    pass


class FileOps:
    """Handles file copy, delete, rename, and soft delete operations."""

    def __init__(self, soft_delete_root: str = ".deleted"):
        """Initialize file operations handler.

        Args:
            soft_delete_root: Root directory for soft-deleted files
        """
        self.soft_delete_root = soft_delete_root

    def copy_file(self, src: str, dst: str, preserve_mtime: bool = True) -> None:
        """Copy file from source to destination.

        Args:
            src: Source file path
            dst: Destination file path
            preserve_mtime: Whether to preserve modification time

        Raises:
            FileOpsError: If copy fails
        """
        try:
            dst_path = Path(dst)

            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(src, dst) if preserve_mtime else shutil.copy(src, dst)

            # Verify copy
            if not dst_path.exists():
                raise FileOpsError(f"Copy verification failed: {dst}")

            logger.info(f"Copied file: {src} -> {dst}")
        except (OSError, IOError, shutil.Error) as e:
            logger.error(f"Failed to copy file {src} to {dst}: {e}")
            raise FileOpsError(f"Copy failed: {e}") from e

    def delete_file(
        self, path: str, soft: bool = True, max_size_bytes: Optional[int] = None
    ) -> None:
        """Delete file, optionally using soft delete.

        Args:
            path: File to delete
            soft: Whether to use soft delete if size allows
            max_size_bytes: Max size for soft delete (None = no limit)

        Raises:
            FileOpsError: If delete fails
        """
        try:
            file_path = Path(path)

            if not file_path.exists():
                logger.warning(f"File does not exist: {path}")
                return

            file_size = file_path.stat().st_size

            # Check if we should soft delete
            should_soft_delete = soft and (max_size_bytes is None or file_size <= max_size_bytes)

            if should_soft_delete:
                self._soft_delete(path)
            else:
                file_path.unlink()
                logger.info(f"Hard deleted file: {path}")
        except (OSError, IOError) as e:
            logger.error(f"Failed to delete file {path}: {e}")
            raise FileOpsError(f"Delete failed: {e}") from e

    def _soft_delete(self, path: str) -> None:
        """Move file to soft delete directory.

        Args:
            path: File to soft delete
        """
        file_path = Path(path)
        soft_delete_path = Path(self.soft_delete_root)
        soft_delete_path.mkdir(parents=True, exist_ok=True)

        # Create timestamped filename to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = file_path.name
        new_name = f"{timestamp}_{original_name}"
        destination = soft_delete_path / new_name

        try:
            # Try rename first (fast, works on same drive)
            file_path.rename(destination)
        except OSError:
            # If rename fails (cross-drive), use copy + delete
            shutil.copy2(str(file_path), str(destination))
            file_path.unlink()

        logger.info(f"Soft deleted file: {path} -> {destination}")

    def rename_file(self, old_path: str, new_path: str) -> None:
        """Rename file.

        Args:
            old_path: Current file path
            new_path: New file path

        Raises:
            FileOpsError: If rename fails
        """
        try:
            old = Path(old_path)
            new = Path(new_path)

            if not old.exists():
                raise FileOpsError(f"Source file does not exist: {old_path}")

            # Ensure destination directory exists
            new.parent.mkdir(parents=True, exist_ok=True)

            old.rename(new)
            logger.info(f"Renamed file: {old_path} -> {new_path}")
        except (OSError, IOError) as e:
            logger.error(f"Failed to rename file {old_path} to {new_path}: {e}")
            raise FileOpsError(f"Rename failed: {e}") from e

    def create_clash_file(self, path: str, is_left: bool = True) -> str:
        """Create a timestamped clash version of a file.

        Args:
            path: Original file path
            is_left: Whether this is the left side copy (unused, kept for compatibility)

        Returns:
            New clash file path

        Raises:
            FileOpsError: If operation fails
        """
        try:
            file_path = Path(path)

            if not file_path.exists():
                raise FileOpsError(f"File does not exist: {path}")

            # Create clash filename: original_name.CONFLICT.timestamp.ext
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = file_path.stem
            suffix = file_path.suffix
            clash_name = f"{stem}.CONFLICT.{timestamp}{suffix}"
            clash_path = file_path.parent / clash_name

            # Copy original to clash location
            shutil.copy2(path, clash_path)
            logger.info(f"Created conflict file: {clash_path}")

            return str(clash_path)
        except (OSError, IOError, shutil.Error) as e:
            logger.error(f"Failed to create conflict file for {path}: {e}")
            raise FileOpsError(f"Conflict creation failed: {e}") from e

    def ensure_directory(self, path: str) -> None:
        """Ensure directory exists.

        Args:
            path: Directory path

        Raises:
            FileOpsError: If creation fails
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except (OSError, IOError) as e:
            logger.error(f"Failed to create directory {path}: {e}")
            raise FileOpsError(f"Directory creation failed: {e}") from e
