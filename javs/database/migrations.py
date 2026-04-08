"""Database initialization and schema migrations for the platform database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from javs.database.schema import CREATE_SCHEMA_MIGRATIONS_TABLE_SQL, MIGRATIONS


def initialize_database(path: Path) -> None:
    """Create the SQLite database file and apply any pending migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        apply_migrations(connection)


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending schema migrations to the provided connection."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(CREATE_SCHEMA_MIGRATIONS_TABLE_SQL)

    applied_versions = {
        row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    for version, statements in MIGRATIONS:
        if version in applied_versions:
            continue

        for statement in statements:
            conn.execute(statement)

        conn.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (version,),
        )

    conn.commit()
