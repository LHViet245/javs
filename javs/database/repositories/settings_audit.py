"""Repository helpers for settings audit history."""

from __future__ import annotations

import sqlite3
from typing import Any

from javs.database.schema import SETTINGS_AUDIT_JSON_FIELDS, dump_json, row_to_dict


class SettingsAuditRepository:
    """Persist settings change snapshots."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_entry(
        self,
        *,
        job_id: str,
        source_path: str,
        config_version: int,
        before_json: object | None = None,
        after_json: object | None = None,
        change_summary_json: object | None = None,
    ) -> int:
        """Insert a settings audit row and return its row ID."""
        cursor = self.connection.execute(
            """
            INSERT INTO settings_audit (
                job_id,
                source_path,
                config_version,
                before_json,
                after_json,
                change_summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                source_path,
                config_version,
                dump_json(before_json),
                dump_json(after_json),
                dump_json(change_summary_json),
            ),
        )
        return int(cursor.lastrowid)

    def list_entries(self) -> list[dict[str, Any]]:
        """Return audit entries in newest-first order."""
        rows = self.connection.execute(
            "SELECT * FROM settings_audit ORDER BY rowid DESC"
        ).fetchall()
        return [row_to_dict(row, json_fields=SETTINGS_AUDIT_JSON_FIELDS) for row in rows]

    def get_for_job(self, job_id: str) -> dict[str, Any] | None:
        """Return the newest audit row for a job, or None when no match exists."""
        row = self.connection.execute(
            "SELECT * FROM settings_audit WHERE job_id = ? ORDER BY rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return row_to_dict(row, json_fields=SETTINGS_AUDIT_JSON_FIELDS)
