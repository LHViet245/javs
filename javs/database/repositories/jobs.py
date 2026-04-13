"""Repository helpers for the jobs table."""

from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from javs.database.schema import JOB_JSON_FIELDS, dump_json, row_to_dict

_UNSET = object()
_MAX_JOB_LIST_LIMIT = 100
_DEFAULT_JOB_LIST_LIMIT = 20
_CURSOR_JSON_FIELDS = ("created_at", "id", "query")


@dataclass(slots=True)
class JobListQuery:
    """Read-side query contract for paginated job history."""

    limit: int | None = None
    cursor: str | None = None
    kind: str | None = None
    status: str | None = None
    origin: str | None = None
    q: str | None = None


@dataclass(slots=True)
class JobListPageRecord:
    """Single page of jobs returned from the repository."""

    items: list[dict[str, Any]] = field(default_factory=list)
    next_cursor: str | None = None


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

    def list_jobs_page(self, query: JobListQuery) -> JobListPageRecord:
        """Return a cursor-paginated page of jobs with optional filtering and search."""
        limit = _normalize_limit(query.limit)
        query_envelope = _query_envelope(query)
        cursor_payload = _decode_cursor(query.cursor) if query.cursor is not None else None
        if cursor_payload is not None and cursor_payload["query"] != query_envelope:
            raise ValueError("cursor query envelope does not match active query")

        where_clauses: list[str] = []
        parameters: list[Any] = []

        for column, value in (
            ("jobs.kind", query.kind),
            ("jobs.status", query.status),
            ("jobs.origin", query.origin),
        ):
            if value is None:
                continue
            where_clauses.append(f"{column} = ?")
            parameters.append(value)

        if query.q is not None and query.q != "":
            search_term = f"%{query.q}%"
            where_clauses.append(
                "("
                "jobs.id LIKE ? COLLATE NOCASE OR "
                "job_items.movie_id LIKE ? COLLATE NOCASE OR "
                "job_items.source_path LIKE ? COLLATE NOCASE OR "
                "job_items.dest_path LIKE ? COLLATE NOCASE"
                ")"
            )
            parameters.extend([search_term, search_term, search_term, search_term])

        if cursor_payload is not None:
            where_clauses.append(
                "(jobs.created_at < ? OR (jobs.created_at = ? AND jobs.id < ?))"
            )
            parameters.extend(
                [
                    cursor_payload["created_at"],
                    cursor_payload["created_at"],
                    cursor_payload["id"],
                ]
            )

        statement = [
            "SELECT DISTINCT jobs.*",
            "FROM jobs",
            "LEFT JOIN job_items ON job_items.job_id = jobs.id",
        ]
        if where_clauses:
            statement.append("WHERE " + " AND ".join(where_clauses))
        statement.append("ORDER BY jobs.created_at DESC, jobs.id DESC")
        statement.append("LIMIT ?")
        parameters.append(limit + 1)

        rows = self.connection.execute(" ".join(statement), parameters).fetchall()
        page_rows = rows[:limit]
        items = [row_to_dict(row, json_fields=JOB_JSON_FIELDS) for row in page_rows]

        next_cursor = None
        if len(rows) > limit and page_rows:
            next_cursor = _encode_cursor(page_rows[-1], query_envelope)

        return JobListPageRecord(items=items, next_cursor=next_cursor)

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


def _normalize_limit(limit: int | None) -> int:
    if limit is None:
        return _DEFAULT_JOB_LIST_LIMIT
    if limit < 1 or limit > _MAX_JOB_LIST_LIMIT:
        raise ValueError("limit must be between 1 and 100")
    return limit


def _query_envelope(query: JobListQuery) -> dict[str, str | None]:
    return {
        "kind": query.kind,
        "status": query.status,
        "origin": query.origin,
        "q": query.q,
    }


def _encode_cursor(row: sqlite3.Row, query_envelope: dict[str, str | None]) -> str:
    payload = {
        "created_at": row["created_at"],
        "id": row["id"],
        "query": query_envelope,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is invalid") from error

    if not isinstance(payload, dict):
        raise ValueError("cursor is invalid")
    if set(payload) != set(_CURSOR_JSON_FIELDS):
        raise ValueError("cursor is invalid")
    if type(payload["created_at"]) is not str or type(payload["id"]) is not str:
        raise ValueError("cursor is invalid")

    query = payload["query"]
    if not isinstance(query, dict):
        raise ValueError("cursor is invalid")
    if set(query) != {"kind", "status", "origin", "q"}:
        raise ValueError("cursor is invalid")

    normalized_query: dict[str, str | None] = {}
    for key in ("kind", "status", "origin", "q"):
        value = query[key]
        if value is not None and type(value) is not str:
            raise ValueError("cursor is invalid")
        normalized_query[key] = value

    return {
        "created_at": payload["created_at"],
        "id": payload["id"],
        "query": normalized_query,
    }
