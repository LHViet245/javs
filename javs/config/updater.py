"""Config updater: updates user configuration file to match the latest default template."""

from __future__ import annotations

from pathlib import Path

from javs.config.loader import get_default_config_path
from javs.utils.logging import get_logger

logger = get_logger(__name__)


def deep_update_dict(base: dict, update: dict) -> None:
    """Recursively update base dictionary with values from update dictionary."""
    for key, val in update.items():
        if isinstance(val, dict) and key in base and isinstance(base[key], dict):
            deep_update_dict(base[key], val)
        else:
            base[key] = val


def sync_user_config() -> bool:
    """Synchronize user's local config with the latest default config template.

    Uses ruamel.yaml to preserve comments and layout.

    Returns:
        True if synchronization was successful or no changes were required.
        False if an error occurred.
    """
    try:
        from ruamel.yaml import YAML
    except ImportError:
        logger.error(
            "sync_config_failed",
            error="ruamel.yaml is not installed. Run: pip install ruamel.yaml"
        )
        return False

    user_config_path = get_default_config_path()

    # Path to the default template packaged with the app
    default_template_path = Path(__file__).parent.parent / "data" / "default_config.yaml"

    if not default_template_path.exists():
        logger.error(
            "sync_config_failed",
            error=f"Default template not found at {default_template_path}"
        )
        return False

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    try:
        with open(default_template_path, encoding="utf-8") as f:
            base_config = yaml.load(f)

        if not user_config_path.exists():
            # If user config doesn't exist, just copy the default template over
            user_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(user_config_path, "w", encoding="utf-8") as f:
                yaml.dump(base_config, f)
            logger.info("config_created", path=str(user_config_path))
            return True

        # Parse user config
        with open(user_config_path, encoding="utf-8") as f:
            user_config = yaml.load(f)

        # Merge user config into base config
        if user_config:
            deep_update_dict(base_config, user_config)

        # Save merged config back to user path
        with open(user_config_path, "w", encoding="utf-8") as f:
            yaml.dump(base_config, f)

        logger.info("config_synced", path=str(user_config_path))
        return True

    except Exception as e:
        logger.error("sync_config_failed", error=str(e))
        return False
