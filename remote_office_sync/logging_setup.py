"""Logging setup for the sync service."""

import getpass
import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    log_file: str,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    rotation_enabled: bool = True,
) -> logging.Logger:
    """Set up logging with file and console handlers.

    Args:
        log_file: Path to log file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        max_bytes: Max size of log file before rotation (in bytes)
        backup_count: Number of backup files to keep
        rotation_enabled: Whether to enable log rotation

    Returns:
        Configured logger instance
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("sync")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Get current user
    try:
        username = getpass.getuser()
    except Exception:
        username = "unknown"

    # File handler with optional rotation
    if rotation_enabled:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
    else:
        file_handler = logging.FileHandler(log_file)

    file_handler.setLevel(getattr(logging, log_level.upper()))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Formatter with username
    formatter = logging.Formatter(
        f"%(asctime)s - %(name)s - %(levelname)s - [{username}] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the configured sync logger."""
    return logging.getLogger("sync")
