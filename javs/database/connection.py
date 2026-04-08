"""SQLite connection and path helpers."""

from __future__ import annotations

from pathlib import Path

from javs.config.models import JavsConfig


def resolve_database_path(config: JavsConfig) -> Path:
    """Return the configured SQLite database path with user expansion applied."""
    return Path(config.database.path).expanduser()
