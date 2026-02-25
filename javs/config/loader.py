"""Config loader: reads YAML files and produces validated JavsConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from javs.config.models import JavsConfig

DEFAULT_CONFIG_FILENAME = "config.yaml"


def get_default_config_dir() -> Path:
    """Return the default config directory (~/.javs/)."""
    return Path.home() / ".javs"


def get_default_config_path() -> Path:
    """Return the default config file path."""
    return get_default_config_dir() / DEFAULT_CONFIG_FILENAME


def load_config(path: Path | None = None) -> JavsConfig:
    """Load and validate config from a YAML file.

    Args:
        path: Path to config file. Uses default if not specified.

    Returns:
        Validated JavsConfig instance.
    """
    if path is None:
        path = get_default_config_path()

    if not path.exists():
        # Return default config if no file exists
        return JavsConfig()

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return JavsConfig(**raw)


def save_config(config: JavsConfig, path: Path | None = None) -> None:
    """Save config to a YAML file.

    Args:
        config: Config to save.
        path: Destination path. Uses default if not specified.
    """
    if path is None:
        path = get_default_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude_defaults=False)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def create_default_config(path: Path | None = None) -> JavsConfig:
    """Create a default config file and return the config.

    Args:
        path: Where to save. Uses default if not specified.

    Returns:
        The default JavsConfig.
    """
    config = JavsConfig()
    save_config(config, path)
    return config
