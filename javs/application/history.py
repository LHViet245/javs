"""History-facing protocols and record conversion helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from javs.application.models import JobDetail, JobItemSummary, JobSummary


class JobHistoryRepository(Protocol):
    """Read-side job repository contract used by the application layer."""

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a stored job row by ID."""

    def list_jobs(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """Return stored job rows in newest-first order."""


class JobItemsHistoryRepository(Protocol):
    """Read-side job item repository contract used by the application layer."""

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Return all stored job item rows for a job."""


def build_job_summary(record: Mapping[str, Any]) -> JobSummary:
    """Convert a repository record into the shared job summary contract."""
    return JobSummary(
        id=str(record["id"]),
        kind=str(record["kind"]),
        status=str(record["status"]),
        origin=str(record["origin"]),
        created_at=record.get("created_at"),
        started_at=record.get("started_at"),
        finished_at=record.get("finished_at"),
        summary=record.get("summary_json"),
        error=record.get("error_json"),
    )


def build_job_item_summary(record: Mapping[str, Any]) -> JobItemSummary:
    """Convert a repository record into the shared job item summary contract."""
    return JobItemSummary(
        id=int(record["id"]),
        item_key=str(record["item_key"]),
        status=str(record["status"]),
        source_path=record.get("source_path"),
        dest_path=record.get("dest_path"),
        movie_id=record.get("movie_id"),
        step=record.get("step"),
        message=record.get("message"),
        metadata=record.get("metadata_json"),
        error=record.get("error_json"),
        created_at=record.get("created_at"),
        started_at=record.get("started_at"),
        finished_at=record.get("finished_at"),
    )


def build_job_detail(
    job_record: Mapping[str, Any],
    item_records: Sequence[Mapping[str, Any]] = (),
) -> JobDetail:
    """Convert stored history records into a shared detail response."""
    return JobDetail(
        job=build_job_summary(job_record),
        result=job_record.get("result_json"),
        items=[build_job_item_summary(record) for record in item_records],
    )
