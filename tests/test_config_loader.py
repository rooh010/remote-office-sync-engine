"""Tests for configuration loader."""

import tempfile
from pathlib import Path

import pytest
import yaml

from remote_office_sync.config_loader import Config, ConfigError, load_config


def test_soft_delete_max_size_null():
    """Test that max_size_mb: null results in None for bytes."""
    config_dict = {
        "left_root": "/left",
        "right_root": "/right",
        "soft_delete": {"enabled": True, "max_size_mb": None},
    }

    config = Config(config_dict)

    assert config.soft_delete_max_size_mb is None
    assert config.soft_delete_max_size_bytes is None


def test_soft_delete_max_size_omitted():
    """Test that omitting max_size_mb results in None."""
    config_dict = {
        "left_root": "/left",
        "right_root": "/right",
        "soft_delete": {"enabled": True},
    }

    config = Config(config_dict)

    assert config.soft_delete_max_size_mb is None
    assert config.soft_delete_max_size_bytes is None


def test_soft_delete_max_size_with_value():
    """Test that max_size_mb with a value works correctly."""
    config_dict = {
        "left_root": "/left",
        "right_root": "/right",
        "soft_delete": {"enabled": True, "max_size_mb": 20},
    }

    config = Config(config_dict)

    assert config.soft_delete_max_size_mb == 20
    assert config.soft_delete_max_size_bytes == 20 * 1024 * 1024


def test_soft_delete_max_size_zero():
    """Test that max_size_mb of 0 works (soft delete nothing)."""
    config_dict = {
        "left_root": "/left",
        "right_root": "/right",
        "soft_delete": {"enabled": True, "max_size_mb": 0},
    }

    config = Config(config_dict)

    assert config.soft_delete_max_size_mb == 0
    assert config.soft_delete_max_size_bytes == 0


def test_config_from_yaml_null_max_size():
    """Test loading config from YAML with null max_size_mb."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(
            {
                "left_root": "/left",
                "right_root": "/right",
                "soft_delete": {"enabled": True, "max_size_mb": None},
            },
            f,
        )
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.soft_delete_max_size_mb is None
        assert config.soft_delete_max_size_bytes is None
    finally:
        Path(config_path).unlink()


def test_config_from_yaml_with_max_size():
    """Test loading config from YAML with max_size_mb value."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(
            {
                "left_root": "/left",
                "right_root": "/right",
                "soft_delete": {"enabled": True, "max_size_mb": 50},
            },
            f,
        )
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.soft_delete_max_size_mb == 50
        assert config.soft_delete_max_size_bytes == 50 * 1024 * 1024
    finally:
        Path(config_path).unlink()


def test_config_missing_required_keys():
    """Test that missing required keys raise ConfigError."""
    config_dict = {"left_root": "/left"}

    with pytest.raises(ConfigError, match="Missing required config key: right_root"):
        Config(config_dict)


def test_dry_run_default_true():
    """Test that dry_run defaults to True when not specified."""
    config_dict = {"left_root": "/left", "right_root": "/right"}

    config = Config(config_dict)

    assert config.dry_run is True


def test_dry_run_explicit_true():
    """Test that dry_run can be explicitly set to True."""
    config_dict = {"left_root": "/left", "right_root": "/right", "dry_run": True}

    config = Config(config_dict)

    assert config.dry_run is True


def test_dry_run_explicit_false():
    """Test that dry_run can be set to False."""
    config_dict = {"left_root": "/left", "right_root": "/right", "dry_run": False}

    config = Config(config_dict)

    assert config.dry_run is False


def test_config_from_yaml_dry_run():
    """Test loading config from YAML with dry_run setting."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(
            {"left_root": "/left", "right_root": "/right", "dry_run": False},
            f,
        )
        config_path = f.name

    try:
        config = load_config(config_path)
        assert config.dry_run is False
    finally:
        Path(config_path).unlink()
