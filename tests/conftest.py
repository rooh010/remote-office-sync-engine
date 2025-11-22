"""Pytest configuration and fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dirs():
    """Create temporary left and right directories for testing."""
    temp_root = Path(tempfile.mkdtemp())
    left = temp_root / "left"
    right = temp_root / "right"
    left.mkdir()
    right.mkdir()

    yield left, right

    # Cleanup
    shutil.rmtree(temp_root, ignore_errors=True)


@pytest.fixture
def sample_config(tmp_path):
    """Create a sample config file for testing."""
    config_path = tmp_path / "config.yaml"
    config_content = """
left_root: /tmp/left
right_root: /tmp/right

soft_delete:
  enabled: true
  max_size_mb: 20

conflict_policy:
  modify_modify: clash
  new_new: clash
  metadata_conflict: clash

ignore:
  extensions:
    - .tmp
    - .bak
  filenames_prefix:
    - .
  filenames_exact:
    - thumbs.db

email:
  enabled: false

logging:
  level: INFO
  file_path: sync.log
"""
    config_path.write_text(config_content)
    return config_path
