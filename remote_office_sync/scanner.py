"""Directory scanner for file metadata collection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


@dataclass
class FileMetadata:
    """Metadata for a single file or directory."""

    relative_path: str
    exists_left: bool
    exists_right: bool
    mtime_left: float | None = None
    mtime_right: float | None = None
    size_left: int | None = None
    size_right: int | None = None

    def __hash__(self) -> int:
        """Hash by relative path."""
        return hash(self.relative_path)

    def __eq__(self, other: object) -> bool:
        """Equality by relative path."""
        if not isinstance(other, FileMetadata):
            return False
        return self.relative_path == other.relative_path

    def is_directory(self) -> bool:
        """Check if this metadata represents a directory (size == -1)."""
        return self.size_left == -1 if self.exists_left else self.size_right == -1


class Scanner:
    """Scans directories and builds metadata snapshots."""

    def __init__(
        self,
        ignore_extensions: List[str] | None = None,
        ignore_filenames_prefix: List[str] | None = None,
        ignore_filenames_exact: List[str] | None = None,
    ):
        """Initialize scanner with ignore rules.

        Args:
            ignore_extensions: Extensions to ignore (e.g., ['.tmp', '.bak'])
            ignore_filenames_prefix: Filename prefixes to ignore
            ignore_filenames_exact: Exact filenames to ignore
        """
        self.ignore_extensions = set(f for f in (ignore_extensions or []) if f)
        self.ignore_filenames_prefix = set(f for f in (ignore_filenames_prefix or []) if f)
        self.ignore_filenames_exact = set(f for f in (ignore_filenames_exact or []) if f)

    def _should_ignore(self, filename: str) -> bool:
        """Check if file should be ignored."""
        # Check exact filename match (case-sensitive)
        if filename in self.ignore_filenames_exact:
            return True

        # Check prefix match (case-sensitive)
        for prefix in self.ignore_filenames_prefix:
            if filename.startswith(prefix):
                return True

        # Check extension match (case-sensitive)
        for ext in self.ignore_extensions:
            if filename.endswith(ext):
                return True

        return False

    def scan_directory(self, root_path: str) -> Dict[str, tuple[float, int]]:
        """Scan a directory and return file metadata.

        Args:
            root_path: Root directory to scan

        Returns:
            Dict mapping relative path to (mtime, size) tuple
            For directories: size is -1 (sentinel value)
        """
        result = {}
        root = Path(root_path)

        if not root.exists():
            logger.warning(f"Directory does not exist: {root_path}")
            return result

        try:
            for file_path in root.rglob("*"):
                if file_path.is_file():
                    # Normalize path separators to forward slashes
                    # Preserve original case - Windows supports case changes
                    relative_path = str(file_path.relative_to(root)).replace("\\", "/")

                    filename = file_path.name

                    if self._should_ignore(filename):
                        logger.debug(f"Ignoring file: {relative_path}")
                        continue

                    try:
                        stat_info = file_path.stat()
                        result[relative_path] = (stat_info.st_mtime, stat_info.st_size)
                    except (OSError, IOError) as e:
                        logger.warning(f"Could not stat file {relative_path}: {e}")
                elif file_path.is_dir():
                    # Track empty directories
                    # Check if directory is empty (no files or subdirectories)
                    if not any(file_path.iterdir()):
                        relative_path = str(file_path.relative_to(root)).replace("\\", "/")

                        # Use -1 as sentinel for directory size
                        try:
                            stat_info = file_path.stat()
                            result[relative_path] = (stat_info.st_mtime, -1)
                            logger.debug(f"Found empty directory: {relative_path}")
                        except (OSError, IOError) as e:
                            logger.warning(f"Could not stat directory {relative_path}: {e}")
        except (OSError, IOError) as e:
            logger.error(f"Error scanning directory {root_path}: {e}")

        logger.info(f"Scanned {len(result)} items (files and empty directories) in {root_path}")
        return result

    def merge_scans(
        self, left_scan: Dict[str, tuple[float, int]], right_scan: Dict[str, tuple[float, int]]
    ) -> Dict[str, FileMetadata]:
        """Merge left and right scans into unified metadata.

        Handles case-insensitive filesystem matching while preserving original case.
        When the same file exists on both sides with different cases, uses the current case
        from whichever side has changed it most recently (based on database state when possible).

        Args:
            left_scan: Results from scanning left directory
            right_scan: Results from scanning right directory

        Returns:
            Dict mapping relative path to FileMetadata
        """
        result = {}

        # Build case-insensitive lookup for right scan
        right_lower_to_actual = {path.lower(): path for path in right_scan.keys()}
        processed_right = set()

        # Process all left files
        for left_path in left_scan.keys():
            left_lower = left_path.lower()

            # Find matching file on right (case-insensitive)
            right_actual_path = right_lower_to_actual.get(left_lower)
            right_exists = right_actual_path is not None

            if right_exists:
                processed_right.add(right_actual_path)

            # Determine canonical case: use left's case
            canonical_path = left_path

            # Store with the canonical (left's) case
            metadata = FileMetadata(
                relative_path=canonical_path,
                exists_left=True,
                exists_right=right_exists,
                mtime_left=left_scan[left_path][0],
                size_left=left_scan[left_path][1],
                mtime_right=right_scan[right_actual_path][0] if right_exists else None,
                size_right=right_scan[right_actual_path][1] if right_exists else None,
            )
            result[canonical_path] = metadata

            # If right has a different case, also create a separate entry for case change detection
            # This entry represents the file as it exists on right with its actual case
            if right_exists and right_actual_path != left_path and right_actual_path not in result:
                # Create metadata entry showing file exists on right with different case
                right_case_metadata = FileMetadata(
                    relative_path=right_actual_path,
                    exists_left=False,  # Not at this case on left
                    exists_right=True,
                    mtime_left=None,
                    size_left=None,
                    mtime_right=right_scan[right_actual_path][0],
                    size_right=right_scan[right_actual_path][1],
                )
                result[right_actual_path] = right_case_metadata

        # Process right files that weren't matched
        for right_path in right_scan.keys():
            if right_path not in processed_right:
                metadata = FileMetadata(
                    relative_path=right_path,  # Use right case since no left match
                    exists_left=False,
                    exists_right=True,
                    mtime_left=None,
                    size_left=None,
                    mtime_right=right_scan[right_path][0],
                    size_right=right_scan[right_path][1],
                )
                result[right_path] = metadata

        logger.info(f"Merged scans: {len(result)} total unique files")
        return result
