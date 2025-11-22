"""Tests for state database module."""

from remote_office_sync.scanner import FileMetadata
from remote_office_sync.state_db import StateDB


class TestStateDB:
    """StateDB tests."""

    def test_init_creates_database(self, tmp_path):
        """Test that initialization creates database file."""
        db_path = tmp_path / "test.db"
        StateDB(str(db_path))

        assert db_path.exists()

    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading state."""
        db_path = tmp_path / "test.db"
        db = StateDB(str(db_path))

        # Create sample state
        state = {
            "file1.txt": FileMetadata(
                relative_path="file1.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
            "file2.txt": FileMetadata(
                relative_path="file2.txt",
                exists_left=True,
                exists_right=False,
                mtime_left=2000.0,
                mtime_right=None,
                size_left=200,
                size_right=None,
            ),
        }

        # Save state
        db.save_state(state)

        # Load and verify
        loaded = db.load_state()
        assert len(loaded) == 2
        assert loaded["file1.txt"].exists_left
        assert loaded["file1.txt"].exists_right
        assert loaded["file2.txt"].exists_left
        assert not loaded["file2.txt"].exists_right

    def test_get_file_state(self, tmp_path):
        """Test getting individual file state."""
        db_path = tmp_path / "test.db"
        db = StateDB(str(db_path))

        state = {
            "file1.txt": FileMetadata(
                relative_path="file1.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }

        db.save_state(state)

        file_state = db.get_file_state("file1.txt")
        assert file_state is not None
        assert file_state.relative_path == "file1.txt"

    def test_nonexistent_file_state(self, tmp_path):
        """Test getting state for non-existent file."""
        db_path = tmp_path / "test.db"
        db = StateDB(str(db_path))

        file_state = db.get_file_state("nonexistent.txt")
        assert file_state is None

    def test_clear_state(self, tmp_path):
        """Test clearing all state."""
        db_path = tmp_path / "test.db"
        db = StateDB(str(db_path))

        state = {
            "file1.txt": FileMetadata(
                relative_path="file1.txt",
                exists_left=True,
                exists_right=True,
                mtime_left=1000.0,
                mtime_right=1000.0,
                size_left=100,
                size_right=100,
            ),
        }

        db.save_state(state)
        db.clear_state()

        loaded = db.load_state()
        assert len(loaded) == 0

    def test_load_empty_database(self, tmp_path):
        """Test loading from empty database."""
        db_path = tmp_path / "test.db"
        db = StateDB(str(db_path))

        loaded = db.load_state()
        assert isinstance(loaded, dict)
        assert len(loaded) == 0
