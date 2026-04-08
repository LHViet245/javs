"""Repository helpers for job events."""

from __future__ import annotations

import sqlite3
from typing import Any

from javs.database.schema import JOB_EVENT_JSON_FIELDS, dump_json, row_to_dict


class JobEventsRepository:
    """Persist job-level and item-level events."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_event(
        self,
        *,
        job_id: str,
        event_type: str,
        job_item_id: int | None = None,
        payload_json: object | None = None,
    ) -> int:
        """Insert an event row and return its row ID."""
        cursor = self.connection.execute(
            """
            INSERT INTO job_events (job_id, job_item_id, event_type, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, job_item_id, event_type, dump_json(payload_json)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Return all events for a job in insertion order."""
        rows = self.connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY rowid ASC",
            (job_id,),
        ).fetchall()
        return [row_to_dict(row, json_fields=JOB_EVENT_JSON_FIELDS) for row in rows]
