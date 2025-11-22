"""Core sync decision engine."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from remote_office_sync.config_loader import Config
from remote_office_sync.conflict import ConflictDetector, ConflictResolution, ConflictType
from remote_office_sync.logging_setup import get_logger
from remote_office_sync.scanner import FileMetadata

logger = get_logger()


class SyncAction(Enum):
    """Sync actions to perform."""

    COPY_LEFT_TO_RIGHT = "COPY_LEFT_TO_RIGHT"
    COPY_RIGHT_TO_LEFT = "COPY_RIGHT_TO_LEFT"
    DELETE_LEFT = "DELETE_LEFT"
    DELETE_RIGHT = "DELETE_RIGHT"
    SOFT_DELETE_LEFT = "SOFT_DELETE_LEFT"
    SOFT_DELETE_RIGHT = "SOFT_DELETE_RIGHT"
    CLASH_CREATE = "CLASH_CREATE"
    RENAME_LEFT = "RENAME_LEFT"
    RENAME_RIGHT = "RENAME_RIGHT"
    NOOP = "NOOP"


@dataclass
class SyncJob:
    """A single sync action to perform."""

    action: SyncAction
    file_path: str
    src_path: Optional[str] = None
    dst_path: Optional[str] = None
    details: Optional[str] = None


class SyncEngine:
    """Sync decision engine."""

    def __init__(
        self,
        config: Config,
        previous_state: Dict[str, FileMetadata],
        current_state: Dict[str, FileMetadata],
    ):
        """Initialize sync engine.

        Args:
            config: Configuration object
            previous_state: File state from last sync
            current_state: Current file state
        """
        self.config = config
        self.previous_state = previous_state
        self.current_state = current_state
        self.conflict_detector = ConflictDetector(previous_state, current_state)

    def generate_sync_jobs(self) -> List[SyncJob]:
        """Generate list of sync jobs to perform.

        Returns:
            List of SyncJob objects
        """
        jobs = []
        processed = set()

        # First detect renames (including case changes)
        rename_map = self._detect_renames()
        for old_path, new_path in rename_map.items():
            processed.add(old_path)
            processed.add(new_path)
            jobs.extend(self._handle_rename(old_path, new_path))

        # Then handle conflicts
        conflicts = self.conflict_detector.detect_conflicts()
        for file_path, (conflict_type, _, curr_metadata) in conflicts.items():
            processed.add(file_path)
            jobs.extend(self._handle_conflict(file_path, conflict_type, curr_metadata))

        # Then handle regular sync rules
        for file_path, curr_metadata in self.current_state.items():
            if file_path in processed:
                continue

            prev_metadata = self.previous_state.get(file_path)
            jobs.extend(self._apply_sync_rules(file_path, prev_metadata, curr_metadata))

        logger.info(f"Generated {len(jobs)} sync jobs")
        return jobs

    def _detect_renames(self) -> Dict[str, str]:
        """Detect file renames by matching size and mtime.

        Returns:
            Dict mapping old_path -> new_path for detected renames
        """
        rename_map = {}

        # Find files that disappeared from previous state
        disappeared = {}
        for prev_path, prev_meta in self.previous_state.items():
            if prev_path not in self.current_state:
                # File disappeared - store by (side, mtime, size) for matching
                if prev_meta.exists_left:
                    key = ("left", prev_meta.mtime_left, prev_meta.size_left)
                    disappeared.setdefault(key, []).append((prev_path, prev_meta))
                if prev_meta.exists_right:
                    key = ("right", prev_meta.mtime_right, prev_meta.size_right)
                    disappeared.setdefault(key, []).append((prev_path, prev_meta))

        # Find files that appeared in current state
        appeared = {}
        for curr_path, curr_meta in self.current_state.items():
            if curr_path not in self.previous_state:
                # File appeared - check if it matches a disappeared file
                if curr_meta.exists_left:
                    key = ("left", curr_meta.mtime_left, curr_meta.size_left)
                    appeared.setdefault(key, []).append((curr_path, curr_meta))
                if curr_meta.exists_right:
                    key = ("right", curr_meta.mtime_right, curr_meta.size_right)
                    appeared.setdefault(key, []).append((curr_path, curr_meta))

        # Match disappeared and appeared files
        for key, appeared_list in appeared.items():
            if key in disappeared:
                disappeared_list = disappeared[key]
                # Simple 1:1 matching - if exactly one disappeared and one appeared
                if len(appeared_list) == 1 and len(disappeared_list) == 1:
                    old_path = disappeared_list[0][0]
                    new_path = appeared_list[0][0]
                    # Only treat as rename if paths differ only in case or are actual renames
                    if old_path.lower() == new_path.lower() or True:  # Accept all renames
                        rename_map[old_path] = new_path
                        logger.info(f"Detected rename: {old_path} -> {new_path}")

        return rename_map

    def _handle_rename(self, old_path: str, new_path: str) -> List[SyncJob]:
        """Handle a detected rename.

        Args:
            old_path: Original file path
            new_path: New file path

        Returns:
            List of sync jobs to propagate the rename
        """
        jobs = []
        curr_meta = self.current_state[new_path]

        # Determine which side has the rename
        if curr_meta.exists_left and not curr_meta.exists_right:
            # Renamed on left - propagate to right
            jobs.append(
                SyncJob(
                    action=SyncAction.COPY_LEFT_TO_RIGHT,
                    file_path=new_path,
                    details=f"Renamed from {old_path}",
                )
            )
            jobs.append(
                SyncJob(
                    action=SyncAction.DELETE_RIGHT,
                    file_path=old_path,
                    details=f"Renamed to {new_path}",
                )
            )
        elif curr_meta.exists_right and not curr_meta.exists_left:
            # Renamed on right - propagate to left
            jobs.append(
                SyncJob(
                    action=SyncAction.COPY_RIGHT_TO_LEFT,
                    file_path=new_path,
                    details=f"Renamed from {old_path}",
                )
            )
            jobs.append(
                SyncJob(
                    action=SyncAction.DELETE_LEFT,
                    file_path=old_path,
                    details=f"Renamed to {new_path}",
                )
            )

        return jobs

    def _handle_conflict(
        self, file_path: str, conflict_type: ConflictType, metadata: FileMetadata
    ) -> List[SyncJob]:
        """Handle a detected conflict.

        Args:
            file_path: Path to conflicted file
            conflict_type: Type of conflict
            metadata: Current file metadata

        Returns:
            List of sync jobs for this conflict
        """
        jobs = []

        # Determine policy based on conflict type
        if conflict_type == ConflictType.MODIFY_MODIFY:
            policy_str = self.config.conflict_policy_modify_modify
        elif conflict_type == ConflictType.NEW_NEW:
            policy_str = self.config.conflict_policy_new_new
        else:
            policy_str = self.config.conflict_policy_metadata_conflict

        # Convert policy string to enum
        policy = {
            "clash": ConflictResolution.CLASH,
            "notify_only": ConflictResolution.NOTIFY_ONLY,
            "overwrite_newer": ConflictResolution.OVERWRITE_NEWER,
        }.get(policy_str, ConflictResolution.CLASH)

        action = self.conflict_detector.resolve_conflict(file_path, conflict_type, policy)

        if action == "CLASH_CREATE":
            jobs.append(
                SyncJob(
                    action=SyncAction.CLASH_CREATE,
                    file_path=file_path,
                    details=f"Conflict type: {conflict_type.value}",
                )
            )
        elif action == "COPY_LEFT_TO_RIGHT":
            jobs.append(
                SyncJob(
                    action=SyncAction.COPY_LEFT_TO_RIGHT,
                    file_path=file_path,
                    details=f"Resolved conflict ({conflict_type.value}): newer on left",
                )
            )
        elif action == "COPY_RIGHT_TO_LEFT":
            jobs.append(
                SyncJob(
                    action=SyncAction.COPY_RIGHT_TO_LEFT,
                    file_path=file_path,
                    details=f"Resolved conflict ({conflict_type.value}): newer on right",
                )
            )
        elif action == "NOTIFY":
            jobs.append(
                SyncJob(
                    action=SyncAction.NOOP,
                    file_path=file_path,
                    details=f"Conflict detected, notify only: {conflict_type.value}",
                )
            )

        return jobs

    def _apply_sync_rules(
        self, file_path: str, prev_metadata: Optional[FileMetadata], curr_metadata: FileMetadata
    ) -> List[SyncJob]:
        """Apply sync rules for a file.

        Args:
            file_path: File path
            prev_metadata: Previous state (None if new file)
            curr_metadata: Current state

        Returns:
            List of sync jobs
        """
        jobs = []

        # Rule: File only on left
        if curr_metadata.exists_left and not curr_metadata.exists_right:
            if prev_metadata is None:
                # New file on left only
                jobs.append(
                    SyncJob(
                        action=SyncAction.COPY_LEFT_TO_RIGHT,
                        file_path=file_path,
                        details="New file on left",
                    )
                )
            elif prev_metadata.exists_right and not curr_metadata.exists_right:
                # Deleted on right, unchanged or changed on left
                if prev_metadata.mtime_left == curr_metadata.mtime_left:
                    # Unchanged on left, deleted on right → follow right's deletion
                    if (
                        self.config.soft_delete_enabled
                        and (prev_metadata.size_right or 0)
                        <= self.config.soft_delete_max_size_bytes
                    ):
                        jobs.append(
                            SyncJob(
                                action=SyncAction.SOFT_DELETE_LEFT,
                                file_path=file_path,
                                details="Deleted on right (unchanged on left)",
                            )
                        )
                    else:
                        jobs.append(
                            SyncJob(
                                action=SyncAction.DELETE_LEFT,
                                file_path=file_path,
                                details="Deleted on right (unchanged on left)",
                            )
                        )
                else:
                    # Changed on left, deleted on right → copy left (left authoritative)
                    jobs.append(
                        SyncJob(
                            action=SyncAction.COPY_LEFT_TO_RIGHT,
                            file_path=file_path,
                            details="Deleted on right but changed on left",
                        )
                    )

        # Rule: File only on right
        elif curr_metadata.exists_right and not curr_metadata.exists_left:
            if prev_metadata is None:
                # New file on right only
                jobs.append(
                    SyncJob(
                        action=SyncAction.COPY_RIGHT_TO_LEFT,
                        file_path=file_path,
                        details="New file on right",
                    )
                )
            elif prev_metadata.exists_left and not curr_metadata.exists_left:
                # Deleted on left, unchanged or changed on right
                if prev_metadata.mtime_right == curr_metadata.mtime_right:
                    # Unchanged on right, deleted on left → follow left's deletion
                    if (
                        self.config.soft_delete_enabled
                        and (prev_metadata.size_left or 0) <= self.config.soft_delete_max_size_bytes
                    ):
                        jobs.append(
                            SyncJob(
                                action=SyncAction.SOFT_DELETE_RIGHT,
                                file_path=file_path,
                                details="Deleted on left (unchanged on right)",
                            )
                        )
                    else:
                        jobs.append(
                            SyncJob(
                                action=SyncAction.DELETE_RIGHT,
                                file_path=file_path,
                                details="Deleted on left (unchanged on right)",
                            )
                        )
                else:
                    # Changed on right, deleted on left → copy right (right authoritative)
                    jobs.append(
                        SyncJob(
                            action=SyncAction.COPY_RIGHT_TO_LEFT,
                            file_path=file_path,
                            details="Deleted on left but changed on right",
                        )
                    )

        # Rule: File on both sides but only one changed
        elif curr_metadata.exists_left and curr_metadata.exists_right:
            left_changed = prev_metadata and (
                (curr_metadata.mtime_left or 0) > (prev_metadata.mtime_left or 0)
            )
            right_changed = prev_metadata and (
                (curr_metadata.mtime_right or 0) > (prev_metadata.mtime_right or 0)
            )

            if left_changed and not right_changed:
                jobs.append(
                    SyncJob(
                        action=SyncAction.COPY_LEFT_TO_RIGHT,
                        file_path=file_path,
                        details="Changed only on left",
                    )
                )
            elif right_changed and not left_changed:
                jobs.append(
                    SyncJob(
                        action=SyncAction.COPY_RIGHT_TO_LEFT,
                        file_path=file_path,
                        details="Changed only on right",
                    )
                )

        return jobs
