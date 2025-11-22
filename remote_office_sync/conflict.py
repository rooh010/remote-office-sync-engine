"""Conflict detection and resolution."""

from enum import Enum
from typing import Optional, Tuple

from remote_office_sync.logging_setup import get_logger
from remote_office_sync.scanner import FileMetadata

logger = get_logger()


class ConflictType(Enum):
    """Types of conflicts that can occur."""

    MODIFY_MODIFY = "modify_modify"
    NEW_NEW = "new_new"
    METADATA_CONFLICT = "metadata_conflict"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""

    CLASH = "clash"
    NOTIFY_ONLY = "notify_only"
    OVERWRITE_NEWER = "overwrite_newer"


class ConflictDetector:
    """Detects and analyzes conflicts in file sync."""

    def __init__(
        self,
        previous_state: dict[str, FileMetadata],
        current_state: dict[str, FileMetadata],
    ):
        """Initialize conflict detector.

        Args:
            previous_state: File state from last sync
            current_state: Current file state
        """
        self.previous_state = previous_state
        self.current_state = current_state

    def detect_conflicts(self) -> dict[str, Tuple[ConflictType, FileMetadata, FileMetadata]]:
        """Detect all conflicts between current and previous state.

        Returns:
            Dict mapping file path to (ConflictType, prev_metadata, curr_metadata)
        """
        conflicts = {}

        for path, curr_metadata in self.current_state.items():
            prev_metadata = self.previous_state.get(path)

            if prev_metadata is None:
                # File is new, check if created on both sides
                if curr_metadata.exists_left and curr_metadata.exists_right:
                    if not self._is_same_content(curr_metadata):
                        logger.debug(
                            f"NEW_NEW conflict for {path}: "
                            f"left_size={curr_metadata.size_left}, "
                            f"right_size={curr_metadata.size_right}, "
                            f"left_mtime={curr_metadata.mtime_left}, "
                            f"right_mtime={curr_metadata.mtime_right}"
                        )
                        conflicts[path] = (ConflictType.NEW_NEW, None, curr_metadata)
                continue

            # Check for modify-modify conflict
            if self._was_modified_both_sides(path, prev_metadata, curr_metadata):
                if not self._is_same_content(curr_metadata):
                    logger.debug(
                        f"MODIFY_MODIFY conflict for {path}: "
                        f"prev: left_mtime={prev_metadata.mtime_left}, "
                        f"right_mtime={prev_metadata.mtime_right}, "
                        f"curr: left_mtime={curr_metadata.mtime_left}, "
                        f"right_mtime={curr_metadata.mtime_right}"
                    )
                    conflicts[path] = (ConflictType.MODIFY_MODIFY, prev_metadata, curr_metadata)

            # Check for metadata conflicts
            if self._has_metadata_conflict(path, prev_metadata, curr_metadata):
                conflicts[path] = (ConflictType.METADATA_CONFLICT, prev_metadata, curr_metadata)

        logger.info(f"Detected {len(conflicts)} conflicts")
        return conflicts

    def _was_modified_both_sides(self, path: str, prev: FileMetadata, curr: FileMetadata) -> bool:
        """Check if file was modified on both sides since last sync.

        Args:
            path: File path
            prev: Previous metadata
            curr: Current metadata

        Returns:
            True if modified on both sides
        """
        left_changed = False
        right_changed = False

        # Check left side change
        if curr.exists_left and prev.mtime_left:
            left_changed = (curr.mtime_left or 0) > prev.mtime_left

        # Check right side change
        if curr.exists_right and prev.mtime_right:
            right_changed = (curr.mtime_right or 0) > prev.mtime_right

        return left_changed and right_changed

    def _is_same_content(self, metadata: FileMetadata) -> bool:
        """Check if file has same content on both sides (size-based heuristic).

        Args:
            metadata: File metadata

        Returns:
            True if content appears identical
        """
        if not metadata.exists_left or not metadata.exists_right:
            return False

        # Simple heuristic: same size and mtime
        same_size = metadata.size_left == metadata.size_right
        same_mtime = metadata.mtime_left == metadata.mtime_right

        return same_size and same_mtime

    def _has_metadata_conflict(self, path: str, prev: FileMetadata, curr: FileMetadata) -> bool:
        """Check if there's a metadata conflict (size mismatch, etc).

        Args:
            path: File path
            prev: Previous metadata
            curr: Current metadata

        Returns:
            True if metadata conflicts
        """
        # Both sides exist but sizes differ (potential corruption)
        if curr.exists_left and curr.exists_right:
            size_mismatch = curr.size_left != curr.size_right
            # Consider it a conflict if sizes differ significantly (more than 1%)
            if size_mismatch and curr.size_left and curr.size_right:
                diff_percent = abs(curr.size_left - curr.size_right) / max(
                    curr.size_left, curr.size_right
                )
                if diff_percent > 0.01:
                    return True

        return False

    def resolve_conflict(
        self,
        path: str,
        conflict_type: ConflictType,
        policy: ConflictResolution,
    ) -> Optional[str]:
        """Resolve a conflict based on policy.

        Args:
            path: File path
            conflict_type: Type of conflict
            policy: Resolution policy

        Returns:
            Action to take, or None if no action
        """
        metadata = self.current_state.get(path)
        if not metadata:
            return None

        if policy == ConflictResolution.NOTIFY_ONLY:
            return "NOTIFY"

        if policy == ConflictResolution.OVERWRITE_NEWER:
            # Use modification time to determine which is newer
            left_mtime = metadata.mtime_left or 0
            right_mtime = metadata.mtime_right or 0

            if left_mtime > right_mtime:
                return "COPY_LEFT_TO_RIGHT"
            elif right_mtime > left_mtime:
                return "COPY_RIGHT_TO_LEFT"
            else:
                return "NOOP"

        # Default to clash
        return "CLASH_CREATE"
