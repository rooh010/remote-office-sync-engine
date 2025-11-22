"""Filesystem utilities for detecting capabilities."""

import shutil
import time
from pathlib import Path

from remote_office_sync.logging_setup import get_logger

logger = get_logger()


def detect_mtime_precision(left_root: str, right_root: str) -> float:
    """Detect the modification time precision difference between two filesystems.

    Creates a temporary test file and copies it between filesystems to measure
    how much precision is lost in modification times.

    Args:
        left_root: Path to left directory
        right_root: Path to right directory

    Returns:
        Maximum safe tolerance in seconds (e.g., 2.0 for network drives)
    """
    try:
        # Create temporary test file on left
        left_path = Path(left_root)
        test_file_left = left_path / ".sync_precision_test.tmp"

        # Write test file with known content
        test_file_left.write_text("precision test", encoding="utf-8")
        time.sleep(0.1)  # Small delay to ensure different mtime

        # Get original mtime
        original_mtime = test_file_left.stat().st_mtime
        logger.debug(f"Original test file mtime: {original_mtime}")

        # Copy to right side
        right_path = Path(right_root)
        test_file_right = right_path / ".sync_precision_test.tmp"
        shutil.copy2(str(test_file_left), str(test_file_right))

        # Get copied mtime
        copied_mtime = test_file_right.stat().st_mtime
        logger.debug(f"Copied test file mtime: {copied_mtime}")

        # Calculate precision loss
        mtime_diff = abs(original_mtime - copied_mtime)
        logger.debug(f"Mtime difference after copy: {mtime_diff} seconds")

        # Clean up test files
        try:
            test_file_left.unlink()
        except Exception:
            pass
        try:
            test_file_right.unlink()
        except Exception:
            pass

        # If difference is >= 1 second, filesystem doesn't preserve sub-second precision
        if mtime_diff >= 1.0:
            tolerance = 2.0  # Use 2 second tolerance for safety
            logger.info(
                f"Filesystem mtime precision loss detected: {mtime_diff:.6f}s. "
                f"Using {tolerance}s tolerance."
            )
            return tolerance
        elif mtime_diff > 0.001:
            # Some precision loss but less than 1 second
            tolerance = max(1.0, mtime_diff * 2)  # Use 2x the observed difference
            logger.info(
                f"Minor mtime precision loss detected: {mtime_diff:.6f}s. "
                f"Using {tolerance}s tolerance."
            )
            return tolerance
        else:
            # No significant precision loss
            tolerance = 0.1  # Use minimal tolerance for clock skew
            logger.info(
                f"No significant mtime precision loss detected. Using {tolerance}s tolerance."
            )
            return tolerance

    except Exception as e:
        # If test fails, use conservative default
        logger.warning(f"Failed to detect mtime precision: {e}. Using default 2s tolerance.")
        return 2.0
