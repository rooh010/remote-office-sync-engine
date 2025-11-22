"""Directory scanner for file metadata collection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


@dataclass
class FileMetadata:
    """Metadata for a single file."""

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
                    # On Windows, normalize case to lowercase (case-insensitive filesystem)
                    relative_path = str(file_path.relative_to(root)).replace("\\", "/")

                    # Windows filesystem is case-insensitive - normalize to lowercase
                    # This prevents treating AAA.doc and aaa.doc as different files
                    import platform

                    if platform.system() == "Windows":
                        relative_path = relative_path.lower()

                    filename = file_path.name

                    if self._should_ignore(filename):
                        logger.debug(f"Ignoring file: {relative_path}")
                        continue

                    try:
                        stat_info = file_path.stat()
                        result[relative_path] = (stat_info.st_mtime, stat_info.st_size)
                    except (OSError, IOError) as e:
                        logger.warning(f"Could not stat file {relative_path}: {e}")
        except (OSError, IOError) as e:
            logger.error(f"Error scanning directory {root_path}: {e}")

        logger.info(f"Scanned {len(result)} files in {root_path}")
        return result

    def merge_scans(
        self, left_scan: Dict[str, tuple[float, int]], right_scan: Dict[str, tuple[float, int]]
    ) -> Dict[str, FileMetadata]:
        """Merge left and right scans into unified metadata.

        Args:
            left_scan: Results from scanning left directory
            right_scan: Results from scanning right directory

        Returns:
            Dict mapping relative path to FileMetadata
        """
        all_paths: Set[str] = set(left_scan.keys()) | set(right_scan.keys())
        result = {}

        for path in all_paths:
            left_exists = path in left_scan
            right_exists = path in right_scan

            metadata = FileMetadata(
                relative_path=path,
                exists_left=left_exists,
                exists_right=right_exists,
                mtime_left=left_scan[path][0] if left_exists else None,
                size_left=left_scan[path][1] if left_exists else None,
                mtime_right=right_scan[path][0] if right_exists else None,
                size_right=right_scan[path][1] if right_exists else None,
            )
            result[path] = metadata

        logger.info(f"Merged scans: {len(result)} total unique files")
        return result
