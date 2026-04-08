"""Database initialization and schema migrations for the platform database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from javs.database.connection import open_database
from javs.database.schema import CREATE_SCHEMA_MIGRATIONS_TABLE_SQL, MIGRATIONS


def initialize_database(path: Path) -> None:
    """Create the SQLite database file and apply any pending migrations."""
    with open_database(path) as connection:
        apply_migrations(connection)


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending schema migrations to the provided connection."""
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
