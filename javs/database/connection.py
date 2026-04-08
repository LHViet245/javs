"""SQLite connection and path helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from javs.config.models import JavsConfig


def resolve_database_path(config: JavsConfig) -> Path:
    """Return the configured SQLite database path with user expansion applied."""
    return Path(config.database.path).expanduser()


def configure_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    """Apply the standard runtime configuration for platform SQLite connections."""
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def open_database(path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection for the provided database path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    return configure_connection(connection)
