"""Core sync decision engine."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
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
    CASE_CONFLICT = "CASE_CONFLICT"
    RENAME_LEFT = "RENAME_LEFT"
    RENAME_RIGHT = "RENAME_RIGHT"
    RENAME_CONFLICT = "RENAME_CONFLICT"
    CREATE_DIR_LEFT = "CREATE_DIR_LEFT"
    CREATE_DIR_RIGHT = "CREATE_DIR_RIGHT"
    DELETE_DIR_LEFT = "DELETE_DIR_LEFT"
    DELETE_DIR_RIGHT = "DELETE_DIR_RIGHT"
    NOOP = "NOOP"


@dataclass
class SyncJob:
    """A single sync action to perform."""

    action: SyncAction
    file_path: str
    src_path: Optional[str] = None
    dst_path: Optional[str] = None
    details: Optional[str] = None
    payload: Optional[dict] = field(default=None, repr=False)


class SyncEngine:
    """Sync decision engine."""

    def __init__(
        self,
        config: Config,
        previous_state: Dict[str, FileMetadata],
        current_state: Dict[str, FileMetadata],
        mtime_tolerance: float = 2.0,
    ):
        """Initialize sync engine.

        Args:
            config: Configuration object
            previous_state: File state from last sync
            current_state: Current file state
            mtime_tolerance: Tolerance in seconds for mtime comparison (default 2.0)
        """
        self.config = config
        self.previous_state = previous_state
        self.current_state = current_state
        self.mtime_tolerance = mtime_tolerance
        self.conflict_detector = ConflictDetector(
            previous_state,
            current_state,
            mtime_tolerance,
            left_root=config.left_root,
            right_root=config.right_root,
        )
        # Cache bytes for case-variant paths so we can preserve older content
        # even if overwritten later
        self.case_snapshot: Dict[str, Optional[bytes]] = {}

    def generate_sync_jobs(self) -> List[SyncJob]:
        """Generate list of sync jobs to perform.

        Returns:
            List of SyncJob objects
        """
        jobs = []
        processed = set()

        # Prime snapshot cache for any paths that had case variants previously.
        # This is best-effort: grab bytes before scanning current state to avoid
        # external overwrites.
        for prev_path in self.previous_state.keys():
            for other in self.previous_state.keys():
                if prev_path != other and prev_path.lower() == other.lower():
                    # We have at least two variants in previous state; snapshot both
                    for variant in (prev_path, other):
                        path_left = Path(self.config.left_root) / variant
                        path_right = Path(self.config.right_root) / variant
                        if path_left.exists():
                            self.case_snapshot[variant] = self._safe_read_bytes(path_left)
                        elif path_right.exists():
                            self.case_snapshot[variant] = self._safe_read_bytes(path_right)

        # First detect case-only changes and case conflicts
        case_changes, case_conflicts = self._detect_case_changes()

        # Handle case conflicts (both sides changed case differently)
        for prev_path, (left_case, right_case) in case_conflicts.items():
            processed.add(prev_path)
            processed.add(left_case)
            processed.add(right_case)
            # Also add lowercase version to catch any merged entries
            processed.add(left_case.lower())
            processed.add(right_case.lower())
            logger.debug(
                f"Added to processed: {prev_path}, {left_case}, {right_case}, "
                f"{left_case.lower()}, {right_case.lower()}"
            )
            # Treat as a rename conflict with different case changes
            jobs.extend(self._handle_case_conflict(prev_path, left_case, right_case))

        # Handle simple case changes (only one side changed case)
        for curr_path, prev_path in case_changes.items():
            processed.add(prev_path)
            processed.add(curr_path)
            jobs.extend(self._handle_case_change(prev_path, curr_path))

        # Then detect renames (including case changes and conflicts)
        rename_map, rename_conflicts = self._detect_renames()

        # Handle rename conflicts
        for old_path, (left_new, right_new) in rename_conflicts.items():
            if old_path in processed or left_new in processed or right_new in processed:
                continue
            processed.add(old_path)
            processed.add(left_new)
            processed.add(right_new)
            jobs.extend(self._handle_rename_conflict(old_path, left_new, right_new))

        # Handle clean renames
        for old_path, new_path in rename_map.items():
            if old_path in processed or new_path in processed:
                continue
            processed.add(old_path)
            processed.add(new_path)
            jobs.extend(self._handle_rename(old_path, new_path))

        # Then handle conflicts
        conflicts = self.conflict_detector.detect_conflicts()
        for file_path, (conflict_type, _, curr_metadata) in conflicts.items():
            processed.add(file_path)
            jobs.extend(self._handle_conflict(file_path, conflict_type, curr_metadata))

        # Then handle regular sync rules for current files
        for file_path, curr_metadata in self.current_state.items():
            if file_path in processed:
                logger.debug(f"Skipping {file_path} (already processed)")
                continue

            # Debug: Check if lowercase version is in processed
            if file_path.lower() in [p.lower() for p in processed]:
                logger.debug(f"Skipping {file_path} (case-insensitive match in processed)")
                continue

            prev_metadata = self.previous_state.get(file_path)
            logger.debug(f"Applying sync rules for {file_path} (not in processed)")
            jobs.extend(self._apply_sync_rules(file_path, prev_metadata, curr_metadata))

        # Handle deleted files and directories (existed in previous state but not current)
        for file_path, prev_metadata in self.previous_state.items():
            if file_path in processed or file_path in self.current_state:
                continue

            # Check if this was a directory
            if prev_metadata.is_directory():
                # Directory was deleted - remove from other side
                if prev_metadata.exists_left and not prev_metadata.exists_right:
                    # Was only on left, now gone -> delete from left
                    jobs.append(
                        SyncJob(
                            action=SyncAction.DELETE_DIR_LEFT,
                            file_path=file_path,
                            details="Empty directory deleted",
                        )
                    )
                elif prev_metadata.exists_right and not prev_metadata.exists_left:
                    # Was only on right, now gone -> delete from right
                    jobs.append(
                        SyncJob(
                            action=SyncAction.DELETE_DIR_RIGHT,
                            file_path=file_path,
                            details="Empty directory deleted",
                        )
                    )
                elif prev_metadata.exists_left and prev_metadata.exists_right:
                    # Was on both sides, now gone -> delete from both
                    jobs.append(
                        SyncJob(
                            action=SyncAction.DELETE_DIR_LEFT,
                            file_path=file_path,
                            details="Empty directory deleted from both sides",
                        )
                    )
                    jobs.append(
                        SyncJob(
                            action=SyncAction.DELETE_DIR_RIGHT,
                            file_path=file_path,
                            details="Empty directory deleted from both sides",
                        )
                    )

        logger.info(f"Generated {len(jobs)} sync jobs")
        for job in jobs:
            logger.debug(
                f"Job: action={job.action.value}, file_path={job.file_path}, "
                f"src_path={job.src_path}"
            )
        return jobs

    def _detect_renames(self) -> tuple[Dict[str, str], Dict[str, tuple[str, str]]]:
        """Detect file renames by matching size and mtime.

        Returns:
            Tuple of (rename_map, rename_conflicts) where:
            - rename_map: old_path -> new_path for clean renames
            - rename_conflicts: old_path -> (left_new_path, right_new_path) for conflicts
        """
        rename_map = {}
        rename_conflicts = {}

        # Track renames by original path to detect conflicts
        renames_by_original = {}

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

                    # Track this rename by original path
                    if old_path not in renames_by_original:
                        renames_by_original[old_path] = []
                    renames_by_original[old_path].append((key[0], new_path))  # (side, new_path)

        # Check for rename conflicts (same file renamed differently on both sides)
        for old_path, renames in renames_by_original.items():
            if len(renames) == 2:
                # Renamed on both sides
                left_rename = next((r for r in renames if r[0] == "left"), None)
                right_rename = next((r for r in renames if r[0] == "right"), None)

                if left_rename and right_rename:
                    left_new = left_rename[1]
                    right_new = right_rename[1]

                    # Check if renamed to different names (case-sensitive comparison)
                    if left_new != right_new:
                        logger.warning(
                            f"Rename conflict detected: {old_path} renamed to "
                            f"{left_new} on left and {right_new} on right"
                        )
                        rename_conflicts[old_path] = (left_new, right_new)
                        continue

            # No conflict - add single rename
            for side, new_path in renames:
                rename_map[old_path] = new_path
                logger.info(f"Detected rename on {side}: {old_path} -> {new_path}")

        return rename_map, rename_conflicts

    def _detect_case_changes(self) -> tuple[Dict[str, str], Dict[str, tuple[str, str]]]:
        """Detect case-only changes and case conflicts.

        This detects when a file's path case has changed on either or both sides.
        Returns:
            Tuple of (case_changes, case_conflicts) where:
            - case_changes: Dict mapping current_path -> previous_path for
              single-side case changes
            - case_conflicts: Dict mapping previous_path -> (left_case,
              right_case) for both-side conflicts
        """
        case_changes = {}
        case_conflicts = {}
        processed = set()

        # Group current state by lowercase to identify case variants
        variants_by_lower = self._group_by_lower_case()

        # Detect case conflicts first: same file with different cases on both sides
        # This happens when both left and right changed case to different values,
        # OR when one side changed case and the other didn't
        for path_lower, variants in variants_by_lower.items():
            if len(variants) == 2:
                # Two case variants exist in current state
                left_var = variants[0]
                right_var = variants[1]
                meta_left = self.current_state[left_var]
                meta_right = self.current_state[right_var]

                # Snapshot bytes now to avoid later overwrites (best-effort)
                for var in variants:
                    path_left = Path(self.config.left_root) / var
                    path_right = Path(self.config.right_root) / var
                    if path_left.exists():
                        self.case_snapshot[var] = self._safe_read_bytes(path_left)
                    elif path_right.exists():
                        self.case_snapshot[var] = self._safe_read_bytes(path_right)

                # Find previous state entry (case-insensitive)
                prev_path = None
                for p in self.previous_state.keys():
                    if p.lower() == path_lower:
                        prev_path = p
                        break

                if prev_path is None:
                    # No previous state - this is a new file with different cases on each side
                    # Treat as new-new conflict, not a case change
                    continue

                # Determine which side(s) changed case from previous state
                left_changed_case = left_var != prev_path and meta_left.exists_left
                right_changed_case = right_var != prev_path and meta_right.exists_right

                if left_changed_case and right_changed_case and left_var != right_var:
                    # BOTH sides changed case to DIFFERENT values - true conflict
                    processed.add(prev_path)
                    processed.add(left_var)
                    processed.add(right_var)
                    logger.warning(
                        f"Case conflict detected: {prev_path} -> "
                        f"{left_var} (left) vs {right_var} (right)"
                    )
                    case_conflicts[prev_path] = (left_var, right_var)

                elif left_changed_case and not right_changed_case:
                    # Only LEFT changed case - treat as conflict
                    # Left has new case, right has old case
                    processed.add(prev_path)
                    processed.add(left_var)
                    processed.add(right_var)
                    logger.warning(
                        f"Case conflict detected: {prev_path} -> "
                        f"{left_var} (left) vs {right_var} (right, unchanged)"
                    )
                    # Store as (left_case, right_case) for conflict handling
                    case_conflicts[prev_path] = (left_var, right_var)

                elif right_changed_case and not left_changed_case:
                    # Only RIGHT changed case - treat as conflict
                    # Right has new case, left has old case
                    processed.add(prev_path)
                    processed.add(left_var)
                    processed.add(right_var)
                    logger.warning(
                        f"Case conflict detected: {prev_path} -> "
                        f"{left_var} (left, unchanged) vs {right_var} (right)"
                    )
                    # Store as (left_case, right_case) for conflict handling
                    case_conflicts[prev_path] = (left_var, right_var)

        # Check for simple case changes (no multiple variants in current state)
        for curr_path, curr_meta in self.current_state.items():
            if curr_path in processed:
                continue

            # Check if there's a previous entry with same path in different case
            prev_meta = self.previous_state.get(curr_path)

            if prev_meta is not None:
                # Exact match exists - no case change for this path
                continue

            # Look for case-insensitive match in previous state
            curr_lower = curr_path.lower()
            for prev_path, prev_meta in self.previous_state.items():
                if prev_path.lower() == curr_lower and prev_path != curr_path:
                    if prev_path not in processed:
                        processed.add(prev_path)
                        processed.add(curr_path)
                        logger.info(
                            f"Detected case change in canonical path: {prev_path} -> {curr_path}"
                        )
                        case_changes[curr_path] = prev_path
                    break

        return case_changes, case_conflicts

    def _group_by_lower_case(self) -> Dict[str, list]:
        """Group current state paths by lowercase variant.

        Returns:
            Dict mapping lowercase path -> list of actual case variants
        """
        grouped = {}
        for path in self.current_state.keys():
            lower = path.lower()
            if lower not in grouped:
                grouped[lower] = []
            grouped[lower].append(path)
        return grouped

    def _safe_read_bytes(self, path: Path) -> Optional[bytes]:
        """Best-effort read of file bytes for snapshotting older content."""
        try:
            return path.read_bytes()
        except (OSError, IOError) as exc:
            logger.warning(f"Unable to read snapshot for {path}: {exc}")
            return None

    def _handle_case_change(self, prev_path: str, curr_path: str) -> List[SyncJob]:
        """Handle a case-only change in file path.

        Args:
            prev_path: Previous file path (old case)
            curr_path: Current file path (new case)

        Returns:
            List of sync jobs to propagate the case change
        """
        jobs = []
        curr_meta = self.current_state[curr_path]

        # Strategy: Determine which side has the new case (curr_path)
        # The side that has curr_path is the one that changed the case
        # We need to propagate the case change to the other side

        # Check if the new case exists on current filesystem (from scanner perspective)
        # Scanner gives us the actual cases for each side
        # curr_meta tells us which sides have the file (case-insensitive match)

        # Since merge_scans uses left as canonical, we use left's case
        # If left has the file, it exists_left will be true with left's case
        # The right side was matched case-insensitively so it exists_right
        # If the right side has a different case, we need to rename it

        # The simplest approach: left is always canonical (uses left case),
        # so we always propagate left's case to right
        if curr_meta.exists_left and curr_meta.exists_right:
            # File exists on both - rename right to match left's case
            jobs.append(
                SyncJob(
                    action=SyncAction.RENAME_RIGHT,
                    file_path=prev_path,
                    dst_path=curr_path,
                    details=f"Case change: {prev_path} -> {curr_path}",
                )
            )
        elif curr_meta.exists_left and not curr_meta.exists_right:
            # File only on left - no need to rename (nothing on right)
            # This shouldn't happen if case change was detected properly
            pass
        elif curr_meta.exists_right and not curr_meta.exists_left:
            # File only on right - rename left to match right's case
            jobs.append(
                SyncJob(
                    action=SyncAction.RENAME_LEFT,
                    file_path=prev_path,
                    dst_path=curr_path,
                    details=f"Case change: {prev_path} -> {curr_path}",
                )
            )

        return jobs

    def _handle_case_conflict(
        self, prev_path: str, left_case: str, right_case: str
    ) -> List[SyncJob]:
        """Handle a case conflict where both sides have different case.

        Creates a conflict file from the OLDER version (by mtime) and keeps
        the NEWER version on both sides.

        Args:
            prev_path: Original file path (from previous state)
            left_case: Case variant on left side
            right_case: Case variant on right side

        Returns:
            List of sync jobs to resolve the conflict
        """
        jobs = []

        logger.warning(
            f"Handling case conflict: {prev_path} -> " f"{left_case} (left) vs {right_case} (right)"
        )

        left_path = Path(self.config.left_root) / left_case
        right_path = Path(self.config.right_root) / right_case

        left_meta = self.current_state.get(left_case)
        right_meta = self.current_state.get(right_case)
        left_mtime = None
        right_mtime = None
        if left_meta:
            left_mtime = left_meta.mtime_left or left_meta.mtime_right
        if right_meta:
            right_mtime = right_meta.mtime_right or right_meta.mtime_left

        # Prefer pre-snapshotted bytes to avoid later overwrites
        left_bytes_snapshot = self.case_snapshot.get(left_case)
        right_bytes_snapshot = self.case_snapshot.get(right_case)

        # Create a CASE_CONFLICT job that will:
        # 1. Compare mtime of left_case vs right_case files
        # 2. Create conflict file from older case variant
        # 3. Keep newer case variant on both sides
        job = SyncJob(
            action=SyncAction.CASE_CONFLICT,
            file_path=left_case,  # Left case (canonical path)
            src_path=right_case,  # Right case (variant path)
            details=f"Case conflict: {left_case} (left) vs {right_case} (right)",
            payload={
                "prev_path": prev_path,
                "left_mtime": left_mtime,
                "right_mtime": right_mtime,
                "left_bytes": (
                    left_bytes_snapshot
                    if left_bytes_snapshot is not None
                    else self._safe_read_bytes(left_path)
                ),
                "right_bytes": (
                    right_bytes_snapshot
                    if right_bytes_snapshot is not None
                    else self._safe_read_bytes(right_path)
                ),
            },
        )
        logger.debug(f"Creating CASE_CONFLICT job: {job}")
        jobs.append(job)

        return jobs

    def _handle_rename_conflict(
        self, old_path: str, left_new: str, right_new: str
    ) -> List[SyncJob]:
        """Handle a rename conflict where file was renamed differently on both sides.

        Args:
            old_path: Original file path
            left_new: New path on left side
            right_new: New path on right side

        Returns:
            List of sync jobs to resolve the conflict
        """
        jobs = []

        # Use left as the "winner" and save right as conflict file
        logger.info(
            f"Handling rename conflict: {old_path} -> {left_new} (left) vs {right_new} (right)"
        )

        # Strategy: Create a special RENAME_CONFLICT action that will:
        # 1. Create conflict file from right version on both sides
        # 2. Keep left version as main on both sides
        jobs.append(
            SyncJob(
                action=SyncAction.RENAME_CONFLICT,
                file_path=right_new,
                src_path=left_new,
                details=f"Rename conflict: {old_path} -> {left_new} (main) vs {right_new}",
            )
        )

        return jobs

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
        """Apply sync rules for a file or directory.

        Args:
            file_path: File or directory path
            prev_metadata: Previous state (None if new file/directory)
            curr_metadata: Current state

        Returns:
            List of sync jobs
        """
        jobs = []

        # Handle directories
        if curr_metadata.is_directory():
            # Empty directory only on left -> create on right
            if curr_metadata.exists_left and not curr_metadata.exists_right:
                jobs.append(
                    SyncJob(
                        action=SyncAction.CREATE_DIR_RIGHT,
                        file_path=file_path,
                        details="New empty directory on left",
                    )
                )
            # Empty directory only on right -> create on left
            elif curr_metadata.exists_right and not curr_metadata.exists_left:
                jobs.append(
                    SyncJob(
                        action=SyncAction.CREATE_DIR_LEFT,
                        file_path=file_path,
                        details="New empty directory on right",
                    )
                )
            # Directory exists on both sides -> no action needed
            return jobs

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
                    if self.config.soft_delete_enabled and (
                        self.config.soft_delete_max_size_bytes is None
                        or (prev_metadata.size_right or 0) <= self.config.soft_delete_max_size_bytes
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
                    if self.config.soft_delete_enabled and (
                        self.config.soft_delete_max_size_bytes is None
                        or (prev_metadata.size_left or 0) <= self.config.soft_delete_max_size_bytes
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

            # Debug logging for change detection
            if prev_metadata:
                logger.debug(f"Change detection for {file_path}:")
                logger.debug(
                    f"  Left: prev_mtime={prev_metadata.mtime_left}, "
                    f"curr_mtime={curr_metadata.mtime_left}, changed={left_changed}"
                )
                logger.debug(
                    f"  Right: prev_mtime={prev_metadata.mtime_right}, "
                    f"curr_mtime={curr_metadata.mtime_right}, changed={right_changed}"
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
