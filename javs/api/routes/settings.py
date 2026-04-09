"""Thin route helpers for settings endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from javs.application import SaveSettingsRequest, SaveSettingsResponse, SettingsResponse
from javs.config.loader import get_default_config_path


def resolve_settings_source_path(source_path: str | None) -> Path:
    """Return the requested settings path or the default config path."""
    if source_path:
        return Path(source_path)
    return get_default_config_path()


def handle_get_settings(facade, source_path: str | None = None) -> SettingsResponse:
    """Read settings through the shared facade."""
    return facade.get_settings(resolve_settings_source_path(source_path))


async def handle_save_settings(
    facade,
    payload: Mapping[str, Any],
) -> SaveSettingsResponse:
    """Persist settings through the shared facade."""
    request = SaveSettingsRequest.model_validate(dict(payload))
    return await facade.save_settings(request, origin="api")
