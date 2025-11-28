"""Directory scanner for file metadata collection."""

import ctypes
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
    attrs_left: int | None = None
    attrs_right: int | None = None

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
        ignore_directories: List[str] | None = None,
    ):
        """Initialize scanner with ignore rules.

        Args:
            ignore_extensions: Extensions to ignore (e.g., ['.tmp', '.bak'])
            ignore_filenames_prefix: Filename prefixes to ignore
            ignore_filenames_exact: Exact filenames to ignore
            ignore_directories: Directory names to ignore (e.g., ['System Volume Information'])
        """
        self.ignore_extensions = set(f for f in (ignore_extensions or []) if f)
        self.ignore_filenames_prefix = set(f for f in (ignore_filenames_prefix or []) if f)
        self.ignore_filenames_exact = set(f for f in (ignore_filenames_exact or []) if f)
        # Normalize directory names to lowercase for case-insensitive comparison on Windows
        self.ignore_directories = set(d.lower() for d in (ignore_directories or []) if d)

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

    def _should_ignore_directory(self, dir_name: str) -> bool:
        """Check if directory should be ignored (case-insensitive on Windows)."""
        return dir_name.lower() in self.ignore_directories

    @staticmethod
    def get_file_attributes(path: Path) -> int:
        """Get Windows file attributes as bitmask.

        Windows attribute constants:
        - FILE_ATTRIBUTE_HIDDEN = 0x2 -> mapped to 0x01
        - FILE_ATTRIBUTE_READONLY = 0x1 -> mapped to 0x02
        - FILE_ATTRIBUTE_ARCHIVE = 0x20 -> mapped to 0x04

        Args:
            path: Path to file

        Returns:
            Bitmask: 0x01=Hidden, 0x02=ReadOnly, 0x04=Archive
            Returns 0 on non-Windows or error
        """
        try:
            # Only works on Windows
            if not hasattr(ctypes, "windll"):
                return 0

            # Get Windows file attributes
            kernel32 = ctypes.windll.kernel32
            get_file_attributes = kernel32.GetFileAttributesW
            get_file_attributes.argtypes = [ctypes.c_wchar_p]
            get_file_attributes.restype = ctypes.c_uint32

            attrs = get_file_attributes(str(path))

            # Invalid handle indicates error
            if attrs == 0xFFFFFFFF:
                return 0

            # Map Windows attributes to our bitmask
            result = 0

            # FILE_ATTRIBUTE_HIDDEN = 0x2 -> our 0x01
            if attrs & 0x2:
                result |= 0x01

            # FILE_ATTRIBUTE_READONLY = 0x1 -> our 0x02
            if attrs & 0x1:
                result |= 0x02

            # FILE_ATTRIBUTE_ARCHIVE = 0x20 -> our 0x04
            if attrs & 0x20:
                result |= 0x04

            return result
        except Exception as e:
            logger.debug(f"Could not get attributes for {path}: {e}")
            return 0

    def scan_directory(self, root_path: str) -> Dict[str, tuple[float, int, int]]:
        """Scan a directory and return file metadata.

        Args:
            root_path: Root directory to scan

        Returns:
            Dict mapping relative path to (mtime, size, attrs) tuple
            For directories: size is -1 (sentinel value), attrs is 0
        """
        result = {}
        root = Path(root_path)

        if not root.exists():
            logger.warning(f"Directory does not exist: {root_path}")
            return result

        try:
            for file_path in root.rglob("*"):
                # Check if any parent directory in the path should be ignored
                relative_path = file_path.relative_to(root)

                # Normalize path separators to forward slashes early
                # Preserve original case - Windows supports case changes
                relative_path_str = str(relative_path).replace("\\", "/")

                should_skip = False
                for part in relative_path.parts[:-1]:  # Check all directories, not the file itself
                    if self._should_ignore_directory(part):
                        logger.debug(f"Skipping path in ignored directory: {relative_path_str}")
                        should_skip = True
                        break

                if should_skip:
                    continue

                if file_path.is_file():

                    filename = file_path.name

                    if self._should_ignore(filename):
                        logger.debug(f"Ignoring file: {relative_path_str}")
                        continue

                    try:
                        stat_info = file_path.stat()
                        attrs = self.get_file_attributes(file_path)
                        result[relative_path_str] = (stat_info.st_mtime, stat_info.st_size, attrs)
                    except (OSError, IOError) as e:
                        logger.warning(f"Could not stat file {relative_path_str}: {e}")
                elif file_path.is_dir():
                    # Track empty directories
                    # Check if directory is empty (no files or subdirectories)
                    if not any(file_path.iterdir()):
                        # Use -1 as sentinel for directory size, 0 for attrs (don't track dir attrs)
                        try:
                            stat_info = file_path.stat()
                            result[relative_path_str] = (stat_info.st_mtime, -1, 0)
                            logger.debug(f"Found empty directory: {relative_path_str}")
                        except (OSError, IOError) as e:
                            logger.warning(f"Could not stat directory {relative_path_str}: {e}")
        except (OSError, IOError) as e:
            logger.error(f"Error scanning directory {root_path}: {e}")

        logger.info(f"Scanned {len(result)} items (files and empty directories) in {root_path}")
        return result

    def merge_scans(
        self,
        left_scan: Dict[str, tuple[float, int, int]],
        right_scan: Dict[str, tuple[float, int, int]],
    ) -> Dict[str, FileMetadata]:
        """Merge left and right scans into unified metadata.

        Handles case-insensitive filesystem matching while preserving original case.
        When the same file exists on both sides with different cases, uses the current case
        from whichever side has changed it most recently (based on database state when possible).

        Args:
            left_scan: Results from scanning left directory (mtime, size, attrs tuples)
            right_scan: Results from scanning right directory (mtime, size, attrs tuples)

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

            # Find matching file on right - prefer exact case match first
            if left_path in right_scan:
                # Exact case match exists
                right_actual_path = left_path
                right_exists = True
            else:
                # Check for case-insensitive match
                potential_right = right_lower_to_actual.get(left_lower)

                # Only use case-insensitive match if no other left file has exact match with it
                # This prevents matching left's "test.txt" to right's "Test.txt" when
                # left also has "Test.txt" that should be the exact match
                if potential_right and potential_right in left_scan:
                    # Another left file has exact match with this right file, don't use it
                    right_actual_path = None
                    right_exists = False
                else:
                    right_actual_path = potential_right
                    right_exists = potential_right is not None

            if right_exists:
                processed_right.add(right_actual_path)

            # Determine canonical case: use left's case
            canonical_path = left_path

            # Store with the canonical (left's) case
            left_attrs = left_scan[left_path][2] if len(left_scan[left_path]) > 2 else None
            right_attrs = (
                right_scan[right_actual_path][2]
                if right_exists and len(right_scan[right_actual_path]) > 2
                else None
            )
            metadata = FileMetadata(
                relative_path=canonical_path,
                exists_left=True,
                exists_right=right_exists,
                mtime_left=left_scan[left_path][0],
                size_left=left_scan[left_path][1],
                attrs_left=left_attrs,
                mtime_right=right_scan[right_actual_path][0] if right_exists else None,
                size_right=right_scan[right_actual_path][1] if right_exists else None,
                attrs_right=right_attrs,
            )
            result[canonical_path] = metadata

            # If right has a different case, also create a separate entry for case change detection
            # This entry represents the file as it exists on right with its actual case
            if right_exists and right_actual_path != left_path and right_actual_path not in result:
                # Create metadata entry showing file exists on right with different case
                right_attrs = (
                    right_scan[right_actual_path][2]
                    if len(right_scan[right_actual_path]) > 2
                    else None
                )
                right_case_metadata = FileMetadata(
                    relative_path=right_actual_path,
                    exists_left=False,  # Not at this case on left
                    exists_right=True,
                    mtime_left=None,
                    size_left=None,
                    attrs_left=None,
                    mtime_right=right_scan[right_actual_path][0],
                    size_right=right_scan[right_actual_path][1],
                    attrs_right=right_attrs,
                )
                result[right_actual_path] = right_case_metadata

        # Process right files that weren't matched
        for right_path in right_scan.keys():
            if right_path not in processed_right:
                right_attrs = right_scan[right_path][2] if len(right_scan[right_path]) > 2 else None
                metadata = FileMetadata(
                    relative_path=right_path,  # Use right case since no left match
                    exists_left=False,
                    exists_right=True,
                    mtime_left=None,
                    size_left=None,
                    attrs_left=None,
                    mtime_right=right_scan[right_path][0],
                    size_right=right_scan[right_path][1],
                    attrs_right=right_attrs,
                )
                result[right_path] = metadata

        logger.info(f"Merged scans: {len(result)} total unique files")
        return result
