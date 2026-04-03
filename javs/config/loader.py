"""Config loader: reads YAML files and produces validated JavsConfig."""

from __future__ import annotations

from pathlib import Path

import yaml

from javs.config.deprecated import find_deprecated_config_paths
from javs.config.migrations import migrate_config_data
from javs.config.models import JavsConfig
from javs.utils.logging import get_logger

DEFAULT_CONFIG_FILENAME = "config.yaml"
logger = get_logger(__name__)


def _merge_config_data(target: dict, update: dict) -> None:
    """Recursively merge config values while preserving existing YAML comments."""
    for key, value in update.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            _merge_config_data(target[key], value)
        else:
            target[key] = value


def _load_ruamel_yaml():
    """Create a ruamel YAML instance configured for comment-preserving writes."""
    from ruamel.yaml import YAML

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    return yaml_rt


def _get_default_template_path() -> Path:
    """Return the packaged default config template path."""
    return Path(__file__).parent.parent / "data" / "default_config.yaml"


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

    deprecated_paths = find_deprecated_config_paths(raw)
    for deprecated_path in deprecated_paths:
        logger.warning("deprecated_config_key_ignored", path=deprecated_path)

    return JavsConfig(**migrate_config_data(raw))


def save_config(config: JavsConfig, path: Path | None = None) -> None:
    """Save config to a YAML file.

    Args:
        config: Config to save.
        path: Destination path. Uses default if not specified.
    """
    if path is None:
        path = get_default_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    data = migrate_config_data(config.model_dump(exclude_defaults=False))
    yaml_rt = _load_ruamel_yaml()

    if path.exists():
        with open(path, encoding="utf-8") as f:
            existing = yaml_rt.load(f) or {}
    else:
        template_path = _get_default_template_path()
        if template_path.exists():
            with open(template_path, encoding="utf-8") as f:
                existing = yaml_rt.load(f) or {}
        else:
            existing = {}

    _merge_config_data(existing, data)

    with open(path, "w", encoding="utf-8") as f:
        yaml_rt.dump(existing, f)


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


def redact_config_for_display(config: JavsConfig) -> dict:
    """Return a JSON-safe config dict with sensitive values masked."""
    data = config.model_dump(exclude_defaults=False)

    if data["sort"]["metadata"]["nfo"]["translate"].get("deepl_api_key"):
        data["sort"]["metadata"]["nfo"]["translate"]["deepl_api_key"] = "***"

    if data["javlibrary"].get("cookie_cf_clearance"):
        data["javlibrary"]["cookie_cf_clearance"] = "***"

    if data["proxy"].get("url"):
        data["proxy"]["url"] = config.proxy.masked_url

    return data
