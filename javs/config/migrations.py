"""Helpers for additive config normalization and version stamping."""

from __future__ import annotations

from typing import Any

from javs.config.models import CURRENT_CONFIG_VERSION


def migrate_config_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize raw config data into the current versioned shape."""
    data = dict(raw or {})
    data["config_version"] = CURRENT_CONFIG_VERSION

    match = data.get("match")
    if isinstance(match, dict):
        normalized_match = dict(match)
        if "mode" not in normalized_match and normalized_match.get("regex_enabled") is True:
            normalized_match["mode"] = "custom"
        data["match"] = normalized_match

    return data
