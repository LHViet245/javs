"""Repository helpers for the jobs table."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from javs.database.schema import JOB_JSON_FIELDS, dump_json, row_to_dict

_UNSET = object()


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


class JobsRepository:
    """Create and retrieve persisted platform job records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_job(
        self,
        *,
        kind: str,
        origin: str,
        request_json: object | None = None,
    ) -> str:
        """Insert a new job row and return its generated ID."""
        job_id = str(uuid4())
        self.connection.execute(
            """
            INSERT INTO jobs (id, kind, status, origin, request_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, kind, "pending", origin, dump_json(request_json)),
        )
        self.connection.commit()
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a single job row, or None when no match exists."""
        row = self.connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return row_to_dict(row, json_fields=JOB_JSON_FIELDS)

    def list_jobs(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Return jobs in newest-first order."""
        statement = "SELECT * FROM jobs ORDER BY rowid DESC"
        parameters: tuple[int, ...] | tuple[()] = ()

        if limit is not None:
            statement = f"{statement} LIMIT ?"
            parameters = (limit,)

        rows = self.connection.execute(statement, parameters).fetchall()
        return [row_to_dict(row, json_fields=JOB_JSON_FIELDS) for row in rows]

    def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        result_json: object = _UNSET,
        summary_json: object = _UNSET,
        error_json: object = _UNSET,
        started_at: str | None | object = _UNSET,
        finished_at: str | None | object = _UNSET,
    ) -> None:
        """Update selected job columns."""
        assignments: list[str] = []
        values: list[object | None] = []

        if status is not None:
            assignments.append("status = ?")
            values.append(status)
        if result_json is not _UNSET:
            assignments.append("result_json = ?")
            values.append(dump_json(result_json))
        if summary_json is not _UNSET:
            assignments.append("summary_json = ?")
            values.append(dump_json(summary_json))
        if error_json is not _UNSET:
            assignments.append("error_json = ?")
            values.append(dump_json(error_json))
        if started_at is not _UNSET:
            assignments.append("started_at = ?")
            values.append(started_at)
        if finished_at is not _UNSET:
            assignments.append("finished_at = ?")
            values.append(finished_at)

        if not assignments:
            return

        values.append(job_id)
        self.connection.execute(
            f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        self.connection.commit()

    def mark_started(self, job_id: str) -> None:
        """Mark a job as running."""
        self.update_job(job_id, status="running", started_at=utc_now())

    def mark_completed(
        self,
        job_id: str,
        *,
        result_json: object | None = None,
        summary_json: object | None = None,
    ) -> None:
        """Mark a job as completed with optional result data."""
        self.update_job(
            job_id,
            status="completed",
            result_json=result_json,
            summary_json=summary_json,
            finished_at=utc_now(),
        )
