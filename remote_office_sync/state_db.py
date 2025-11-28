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
        """Initialize database schema and run migrations."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Create schema_version table if it doesn't exist
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create files table if it doesn't exist (v1 schema)
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

            # Run any pending migrations
            self._migrate_schema(conn)

            logger.info(f"Initialized state database at {self.db_path}")
        finally:
            conn.close()

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version.

        Args:
            conn: Database connection

        Returns:
            Current schema version, or 1 if table is empty (initial version)
        """
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            if result and result[0]:
                return result[0]
            return 1  # Default to v1 if no version recorded
        except sqlite3.Error:
            return 1

    def _get_table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        """Get list of columns in a table.

        Args:
            conn: Database connection
            table_name: Name of table

        Returns:
            Set of column names
        """
        try:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            return {row[1] for row in cursor.fetchall()}
        except sqlite3.Error:
            return set()

    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        """Record schema version.

        Args:
            conn: Database connection
            version: Version number
        """
        conn.execute("DELETE FROM schema_version")  # Keep only latest version
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Run all pending schema migrations.

        Args:
            conn: Database connection
        """
        current_version = self._get_schema_version(conn)

        # Migrate to v2 if needed (add attribute columns)
        if current_version < 2:
            self._migrate_to_v2(conn)

    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        """Migrate schema to v2: Add attrs_left and attrs_right columns.

        Args:
            conn: Database connection
        """
        columns = self._get_table_columns(conn, "files")

        # Add attrs_left column if it doesn't exist
        if "attrs_left" not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN attrs_left INTEGER")
            logger.info("Added attrs_left column to files table")

        # Add attrs_right column if it doesn't exist
        if "attrs_right" not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN attrs_right INTEGER")
            logger.info("Added attrs_right column to files table")

        # Record the migration
        self._set_schema_version(conn, 2)
        logger.info("Migrated schema to v2")

    def load_state(self) -> Dict[str, FileMetadata]:
        """Load previous state from database.

        Returns:
            Dict mapping relative path to FileMetadata
        """
        result = {}

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            # Query all columns that exist
            cursor = conn.execute("SELECT * FROM files")
            for row in cursor.fetchall():
                # Extract values based on column count
                # Old schema has 7 columns, new has 9
                if len(row) >= 9:
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                        attrs_left,
                        attrs_right,
                    ) = row[:9]
                else:
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                    ) = row
                    attrs_left = None
                    attrs_right = None

                metadata = FileMetadata(
                    relative_path=path,
                    exists_left=bool(exists_left),
                    exists_right=bool(exists_right),
                    mtime_left=mtime_left,
                    mtime_right=mtime_right,
                    size_left=size_left,
                    size_right=size_right,
                    attrs_left=attrs_left,
                    attrs_right=attrs_right,
                )
                result[path] = metadata

            logger.info(f"Loaded state for {len(result)} files from database")
        except sqlite3.Error as e:
            logger.warning(f"Error loading state from database: {e}")
        finally:
            if conn:
                conn.close()

        return result

    def save_state(self, state: Dict[str, FileMetadata]) -> None:
        """Save current state to database.

        Args:
            state: Dict mapping relative path to FileMetadata
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
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
                    metadata.attrs_left,
                    metadata.attrs_right,
                )
                for metadata in state.values()
            ]

            sql = """
                INSERT INTO files
                (path, exists_left, exists_right, mtime_left,
                 mtime_right, size_left, size_right, attrs_left, attrs_right)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            conn.executemany(sql, data)
            conn.commit()

            logger.info(f"Saved state for {len(state)} files to database")
        except sqlite3.Error as e:
            logger.error(f"Error saving state to database: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_file_state(self, path: str) -> Optional[FileMetadata]:
        """Get state for a specific file.

        Args:
            path: Relative file path

        Returns:
            FileMetadata if found, None otherwise
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT * FROM files WHERE path = ?", (path,))
            row = cursor.fetchone()

            if row:
                # Extract values based on column count
                # Old schema has 7 columns, new has 9
                if len(row) >= 9:
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                        attrs_left,
                        attrs_right,
                    ) = row[:9]
                else:
                    (
                        path,
                        exists_left,
                        exists_right,
                        mtime_left,
                        mtime_right,
                        size_left,
                        size_right,
                    ) = row
                    attrs_left = None
                    attrs_right = None

                return FileMetadata(
                    relative_path=path,
                    exists_left=bool(exists_left),
                    exists_right=bool(exists_right),
                    mtime_left=mtime_left,
                    mtime_right=mtime_right,
                    size_left=size_left,
                    size_right=size_right,
                    attrs_left=attrs_left,
                    attrs_right=attrs_right,
                )
        except sqlite3.Error as e:
            logger.warning(f"Error getting file state: {e}")
        finally:
            if conn:
                conn.close()

        return None

    def clear_state(self) -> None:
        """Clear all state from database."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM files")
            conn.commit()
            logger.info("Cleared all state from database")
        except sqlite3.Error as e:
            logger.error(f"Error clearing state: {e}")
            raise
        finally:
            if conn:
                conn.close()
