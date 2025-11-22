"""State database for tracking sync history."""

import sqlite3
from typing import Dict, Optional

from remote_office_sync.logging_setup import get_logger
from remote_office_sync.scanner import FileMetadata

logger = get_logger()


class StateDB:
    """SQLite database for tracking file sync state."""

    def __init__(self, db_path: str = "sync_state.db"):
        """Initialize state database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    exists_left INTEGER,
                    exists_right INTEGER,
                    mtime_left REAL,
                    mtime_right REAL,
                    size_left INTEGER,
                    size_right INTEGER
                )
                """
            )
            conn.commit()
            logger.info(f"Initialized state database at {self.db_path}")

    def load_state(self) -> Dict[str, FileMetadata]:
        """Load previous state from database.

        Returns:
            Dict mapping relative path to FileMetadata
        """
        result = {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM files")
                for row in cursor.fetchall():
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                    ) = row
                    metadata = FileMetadata(
                        relative_path=path,
                        exists_left=bool(exists_left),
                        exists_right=bool(exists_right),
                        mtime_left=mtime_left,
                        mtime_right=mtime_right,
                        size_left=size_left,
                        size_right=size_right,
                    )
                    result[path] = metadata

            logger.info(f"Loaded state for {len(result)} files from database")
        except sqlite3.Error as e:
            logger.warning(f"Error loading state from database: {e}")

        return result

    def save_state(self, state: Dict[str, FileMetadata]) -> None:
        """Save current state to database.

        Args:
            state: Dict mapping relative path to FileMetadata
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM files")

                data = [
                    (
                        metadata.relative_path,
                        int(metadata.exists_left),
                        int(metadata.exists_right),
                        metadata.mtime_left,
                        metadata.mtime_right,
                        metadata.size_left,
                        metadata.size_right,
                    )
                    for metadata in state.values()
                ]

                sql = """
                    INSERT INTO files
                    (path, exists_left, exists_right, mtime_left,
                     mtime_right, size_left, size_right)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                conn.executemany(sql, data)
                conn.commit()

            logger.info(f"Saved state for {len(state)} files to database")
        except sqlite3.Error as e:
            logger.error(f"Error saving state to database: {e}")
            raise

    def get_file_state(self, path: str) -> Optional[FileMetadata]:
        """Get state for a specific file.

        Args:
            path: Relative file path

        Returns:
            FileMetadata if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM files WHERE path = ?", (path,))
                row = cursor.fetchone()

                if row:
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                    ) = row
                    return FileMetadata(
                        relative_path=path,
                        exists_left=bool(exists_left),
                        exists_right=bool(exists_right),
                        mtime_left=mtime_left,
                        mtime_right=mtime_right,
                        size_left=size_left,
                        size_right=size_right,
                    )
        except sqlite3.Error as e:
            logger.warning(f"Error getting file state: {e}")

        return None

    def clear_state(self) -> None:
        """Clear all state from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM files")
                conn.commit()
            logger.info("Cleared all state from database")
        except sqlite3.Error as e:
            logger.error(f"Error clearing state: {e}")
            raise
