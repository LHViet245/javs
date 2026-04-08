"""Repository helpers for job item records."""

from __future__ import annotations

import sqlite3
from typing import Any

from javs.database.schema import JOB_ITEM_JSON_FIELDS, dump_json, row_to_dict


class JobItemsRepository:
    """Persist file-level job items."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_item(
        self,
        *,
        job_id: str,
        item_key: str,
        status: str,
        source_path: str | None = None,
        dest_path: str | None = None,
        movie_id: str | None = None,
        step: str | None = None,
        message: str | None = None,
        metadata_json: object | None = None,
        error_json: object | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> int:
        """Insert a job item and return its row ID."""
        cursor = self.connection.execute(
            """
            INSERT INTO job_items (
                job_id,
                item_key,
                source_path,
                dest_path,
                movie_id,
                status,
                step,
                message,
                metadata_json,
                error_json,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                item_key,
                source_path,
                dest_path,
                movie_id,
                status,
                step,
                message,
                dump_json(metadata_json),
                dump_json(error_json),
                started_at,
                finished_at,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Return all items for a job in insertion order."""
        rows = self.connection.execute(
            "SELECT * FROM job_items WHERE job_id = ? ORDER BY rowid ASC",
            (job_id,),
        ).fetchall()
        return [row_to_dict(row, json_fields=JOB_ITEM_JSON_FIELDS) for row in rows]
