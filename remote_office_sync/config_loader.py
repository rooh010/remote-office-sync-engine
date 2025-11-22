"""Configuration loader for the sync service."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigError(Exception):
    """Raised when config validation fails."""

    pass


class Config:
    """Configuration object for the sync service."""

    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize config from dictionary."""
        self._config = config_dict
        self._validate()

    def _validate(self) -> None:
        """Validate required configuration fields."""
        required_keys = ["left_root", "right_root"]
        for key in required_keys:
            if key not in self._config:
                raise ConfigError(f"Missing required config key: {key}")

            path = self._config[key]
            if not isinstance(path, str):
                raise ConfigError(f"Config key '{key}' must be a string")

    @property
    def left_root(self) -> str:
        """Get left root path."""
        return self._config["left_root"]

    @property
    def right_root(self) -> str:
        """Get right root path."""
        return self._config["right_root"]

    @property
    def soft_delete_enabled(self) -> bool:
        """Get soft delete enabled flag."""
        return self._config.get("soft_delete", {}).get("enabled", True)

    @property
    def soft_delete_max_size_mb(self) -> int:
        """Get soft delete max size in MB."""
        return self._config.get("soft_delete", {}).get("max_size_mb", 20)

    @property
    def soft_delete_max_size_bytes(self) -> int:
        """Get soft delete max size in bytes."""
        return self.soft_delete_max_size_mb * 1024 * 1024

    @property
    def conflict_policy_modify_modify(self) -> str:
        """Get conflict policy for file modified on both sides."""
        return self._config.get("conflict_policy", {}).get("modify_modify", "clash")

    @property
    def conflict_policy_new_new(self) -> str:
        """Get conflict policy for file created on both sides with different content."""
        return self._config.get("conflict_policy", {}).get("new_new", "clash")

    @property
    def conflict_policy_metadata_conflict(self) -> str:
        """Get conflict policy for metadata conflicts."""
        return self._config.get("conflict_policy", {}).get("metadata_conflict", "clash")

    @property
    def email_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return self._config.get("email", {}).get("enabled", False)

    @property
    def email_smtp_host(self) -> Optional[str]:
        """Get SMTP host."""
        return self._config.get("email", {}).get("smtp_host")

    @property
    def email_smtp_port(self) -> int:
        """Get SMTP port."""
        return self._config.get("email", {}).get("smtp_port", 587)

    @property
    def email_username(self) -> Optional[str]:
        """Get SMTP username."""
        return self._config.get("email", {}).get("username")

    @property
    def email_password(self) -> Optional[str]:
        """Get SMTP password."""
        return self._config.get("email", {}).get("password")

    @property
    def email_from(self) -> Optional[str]:
        """Get from email address."""
        return self._config.get("email", {}).get("from")

    @property
    def email_to(self) -> list:
        """Get to email addresses."""
        return self._config.get("email", {}).get("to", [])

    @property
    def ignore_extensions(self) -> list:
        """Get extensions to ignore."""
        items = self._config.get("ignore", {}).get("extensions", [])
        return [i for i in (items or []) if i]

    @property
    def ignore_filenames_prefix(self) -> list:
        """Get filename prefixes to ignore."""
        items = self._config.get("ignore", {}).get("filenames_prefix", [])
        return [i for i in (items or []) if i]

    @property
    def ignore_filenames_exact(self) -> list:
        """Get exact filenames to ignore."""
        items = self._config.get("ignore", {}).get("filenames_exact", [])
        return [i for i in (items or []) if i]

    @property
    def log_file_path(self) -> str:
        """Get log file path."""
        return self._config.get("logging", {}).get("file_path", "sync.log")

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self._config.get("logging", {}).get("level", "INFO")

    def to_dict(self) -> Dict[str, Any]:
        """Return config as dictionary."""
        return self._config.copy()


def load_config(config_path: str) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Config object

    Raises:
        ConfigError: If config file doesn't exist or is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config_dict = yaml.safe_load(f) or {}

    return Config(config_dict)


def load_config_from_env(env_var: str = "SYNC_CONFIG") -> Config:
    """Load configuration from environment variable.

    Args:
        env_var: Name of environment variable containing config path

    Returns:
        Config object

    Raises:
        ConfigError: If environment variable not set or config invalid
    """
    config_path = os.getenv(env_var)
    if not config_path:
        raise ConfigError(f"Environment variable {env_var} not set")

    return load_config(config_path)
