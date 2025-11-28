"""File operations layer for sync actions."""

import ctypes
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

    def set_file_attributes(self, path: str, attrs: int) -> bool:
        """Set Windows file attributes from bitmask.

        Args:
            path: Path to file
            attrs: Bitmask (0x01=Hidden, 0x02=ReadOnly, 0x04=Archive)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Only works on Windows
            if not hasattr(ctypes, "windll"):
                return False

            kernel32 = ctypes.windll.kernel32
            set_attrs = kernel32.SetFileAttributesW
            set_attrs.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
            set_attrs.restype = ctypes.c_bool

            # Convert our bitmask to Windows attribute flags
            win_attrs = 0x80  # FILE_ATTRIBUTE_NORMAL base

            if attrs & 0x01:  # Hidden
                win_attrs |= 0x2  # FILE_ATTRIBUTE_HIDDEN

            if attrs & 0x02:  # ReadOnly
                win_attrs |= 0x1  # FILE_ATTRIBUTE_READONLY

            if attrs & 0x04:  # Archive
                win_attrs |= 0x20  # FILE_ATTRIBUTE_ARCHIVE

            result = set_attrs(str(path), win_attrs)
            if result:
                logger.debug(f"Set attributes 0x{attrs:02x} on {path}")
            else:
                logger.warning(f"Failed to set attributes on {path}")

            return result
        except Exception as e:
            logger.debug(f"Could not set attributes on {path}: {e}")
            return False

    def copy_file(
        self, src: str, dst: str, preserve_mtime: bool = True, preserve_attrs: bool = True
    ) -> None:
        """Copy file from source to destination.

        Args:
            src: Source file path
            dst: Destination file path
            preserve_mtime: Whether to preserve modification time
            preserve_attrs: Whether to preserve file attributes

        Raises:
            FileOpsError: If copy fails
        """
        try:
            src_path = Path(src)
            dst_path = Path(dst)

            # Skip unnecessary work if source and destination point to same file
            try:
                if src_path.resolve() == dst_path.resolve():
                    logger.debug(f"Skipped copy; source and destination are identical: {src}")
                    return
            except OSError:
                # Fall back to normal copy if resolution fails (e.g., missing parent dirs)
                pass

            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            (
                shutil.copy2(str(src_path), str(dst_path))
                if preserve_mtime
                else shutil.copy(str(src_path), str(dst_path))
            )

            # Verify copy
            if not dst_path.exists():
                raise FileOpsError(f"Copy verification failed: {dst}")

            # Preserve attributes if requested
            if preserve_attrs:
                from remote_office_sync.scanner import Scanner

                src_attrs = Scanner.get_file_attributes(src_path)
                if src_attrs:
                    self.set_file_attributes(str(dst_path), src_attrs)

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

    def create_clash_file(
        self, path: str, is_left: bool = True, username: Optional[str] = None
    ) -> str:
        """Create a timestamped clash version of a file.

        Args:
            path: Original file path
            is_left: Whether this is the left side copy (unused, kept for compatibility)
            username: Username to include in conflict filename

        Returns:
            New clash file path

        Raises:
            FileOpsError: If operation fails
        """
        try:
            file_path = Path(path)

            if not file_path.exists():
                raise FileOpsError(f"File does not exist: {path}")

            # Create clash filename with optional username
            # Format: original_name.CONFLICT.username.timestamp.ext
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = file_path.stem
            suffix = file_path.suffix

            if username:
                clash_name = f"{stem}.CONFLICT.{username}.{timestamp}{suffix}"
            else:
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
