"""History-facing contracts and read helpers for the application layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from javs.config import JavsConfig

from .models import (
    JobDetail as LegacyJobDetail,
)
from .models import (
    JobItemSummary as LegacyJobItemSummary,
)
from .models import (
    JobSummary as LegacyJobSummary,
)


def _normalize_optional_text(value: object, *, lower: bool = False) -> str | None:
    """Return a normalized string filter or ``None`` when the input is empty."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    return text.lower() if lower else text


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


class JobEventsHistoryRepository(Protocol):
    """Read-side job event repository contract used by the application layer."""

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        """Return all stored event rows for a job."""


class SettingsAuditHistoryRepository(Protocol):
    """Read-side settings audit repository contract used by the application layer."""

    def list_entries(self) -> list[dict[str, Any]]:
        """Return all stored audit rows."""


class JobListQuery(BaseModel):
    """Cursor-based job list query parameters."""

    model_config = ConfigDict(extra="ignore")

    limit: int = 20
    cursor: str | None = None
    kind: str | None = None
    status: str | None = None
    origin: str | None = None
    q: str | None = None

    @field_validator("cursor", mode="before")
    @classmethod
    def normalize_cursor(cls, value: object) -> object:
        return _normalize_optional_text(value)

    @field_validator("kind", "status", "origin", mode="before")
    @classmethod
    def normalize_filters(cls, value: object) -> object:
        return _normalize_optional_text(value, lower=True)

    @field_validator("q", mode="before")
    @classmethod
    def normalize_query(cls, value: object) -> object:
        return _normalize_optional_text(value)


class JobSummaryPayload(BaseModel):
    """Normalized summary payload with stable consumer-facing keys."""

    model_config = ConfigDict(extra="allow")

    total: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    warnings: list[str] = Field(default_factory=list)

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            return [str(item) for item in value if str(item)]
        return value


class JobSummary(LegacyJobSummary):
    """Top-level summary returned for jobs and job lists."""


class JobItemSummary(LegacyJobItemSummary):
    """Item-level progress summary for sort and update jobs."""


class JobEventSummary(BaseModel):
    """Typed job event payload used by realtime notifications and history views."""

    id: int
    job_id: str
    event_type: str
    job_item_id: int | None = None
    payload: dict[str, Any] | None = None
    created_at: str | None = None


class SettingsAuditEntry(BaseModel):
    """Typed settings audit row exposed by history reads."""

    id: int
    job_id: str
    source_path: str
    config_version: int
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    change_summary: dict[str, Any] | None = None
    created_at: str | None = None


class JobDetail(LegacyJobDetail):
    """Expanded job details, including stored result, item history, and related events."""

    job: JobSummary
    result: dict[str, Any] | None = None
    items: list[JobItemSummary] = Field(default_factory=list)
    events: list[JobEventSummary] = Field(default_factory=list)
    settings_audit: list[SettingsAuditEntry] = Field(default_factory=list)


class JobListPage(BaseModel):
    """Paged job list returned from the history read path."""

    items: list[JobSummary] = Field(default_factory=list)
    next_cursor: str | None = None


class SettingsView(BaseModel):
    """Typed settings snapshot returned by the history read path."""

    config: JavsConfig
    source_path: str
    config_version: int
    settings_audit: list[SettingsAuditEntry] = Field(default_factory=list)


class RealtimeEvent(BaseModel):
    """Realtime event envelope emitted from the application layer."""

    type: str
    job_id: str
    event: JobEventSummary


def normalize_job_summary_payload(value: object | None) -> dict[str, Any]:
    """Return a stable summary payload shape with default consumer keys."""
    if value is None:
        return JobSummaryPayload().model_dump(mode="python")

    payload = JobSummaryPayload.model_validate(value)
    return payload.model_dump(mode="python")


def build_job_summary(
    record: Mapping[str, Any],
    *,
    normalize_summary: bool = False,
) -> JobSummary:
    """Convert a repository record into the shared job summary contract."""
    summary = record.get("summary_json")
    if normalize_summary:
        summary = normalize_job_summary_payload(summary)
    return JobSummary(
        id=str(record["id"]),
        kind=str(record["kind"]),
        status=str(record["status"]),
        origin=str(record["origin"]),
        created_at=record.get("created_at"),
        started_at=record.get("started_at"),
        finished_at=record.get("finished_at"),
        summary=summary,
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


def build_job_event_summary(record: Mapping[str, Any]) -> JobEventSummary:
    """Convert a repository record into the shared job event summary contract."""
    return JobEventSummary(
        id=int(record["id"]),
        job_id=str(record["job_id"]),
        event_type=str(record["event_type"]),
        job_item_id=record.get("job_item_id"),
        payload=record.get("payload_json"),
        created_at=record.get("created_at"),
    )


def build_settings_audit_entry(record: Mapping[str, Any]) -> SettingsAuditEntry:
    """Convert a repository record into the shared settings audit contract."""
    return SettingsAuditEntry(
        id=int(record["id"]),
        job_id=str(record["job_id"]),
        source_path=str(record["source_path"]),
        config_version=int(record["config_version"]),
        before=record.get("before_json"),
        after=record.get("after_json"),
        change_summary=record.get("change_summary_json"),
        created_at=record.get("created_at"),
    )


def build_realtime_event(
    *,
    type: str,
    job_id: str,
    event_record: Mapping[str, Any],
) -> RealtimeEvent:
    """Build a realtime event envelope from a persisted event row."""
    return RealtimeEvent(
        type=type,
        job_id=job_id,
        event=build_job_event_summary(event_record),
    )


def build_job_detail(
    job_record: Mapping[str, Any],
    item_records: Sequence[Mapping[str, Any]] = (),
    event_records: Sequence[Mapping[str, Any]] = (),
    settings_audit_records: Sequence[Mapping[str, Any]] = (),
) -> JobDetail:
    """Convert stored history records into a shared detail response."""
    return JobDetail(
        job=build_job_summary(job_record, normalize_summary=True),
        result=job_record.get("result_json"),
        items=[build_job_item_summary(record) for record in item_records],
        events=[build_job_event_summary(record) for record in event_records],
        settings_audit=[
            build_settings_audit_entry(record) for record in settings_audit_records
        ],
    )


def _job_matches_query(record: Mapping[str, Any], query: JobListQuery) -> bool:
    """Return ``True`` when a record matches the normalized list query."""
    for field in ("kind", "status", "origin"):
        expected = getattr(query, field)
        if expected is None:
            continue
        if str(record.get(field, "")).strip().lower() != expected:
            return False

    if query.q is not None:
        haystack_parts = [
            str(record.get("id", "")),
            str(record.get("kind", "")),
            str(record.get("status", "")),
            str(record.get("origin", "")),
            str(record.get("summary_json", "")),
            str(record.get("result_json", "")),
            str(record.get("error_json", "")),
        ]
        haystack = " ".join(haystack_parts).lower()
        if query.q.lower() not in haystack:
            return False

    return True


def _apply_cursor(
    records: Sequence[Mapping[str, Any]],
    cursor: str | None,
) -> list[Mapping[str, Any]]:
    """Return records that appear after the matching cursor row."""
    if cursor is None:
        return list(records)

    for index, record in enumerate(records):
        if str(record.get("id")) == cursor:
            return list(records[index + 1 :])
    return list(records)


def list_jobs(
    jobs: JobHistoryRepository,
    query: JobListQuery | None = None,
) -> JobListPage:
    """Return a typed page of jobs for history consumers."""
    active_query = query or JobListQuery()
    should_fetch_all = any(
        value is not None
        for value in (
            active_query.cursor,
            active_query.kind,
            active_query.status,
            active_query.origin,
            active_query.q,
        )
    )
    raw_jobs = jobs.list_jobs(limit=None if should_fetch_all else active_query.limit)
    filtered_jobs = [record for record in raw_jobs if _job_matches_query(record, active_query)]
    paged_jobs = _apply_cursor(filtered_jobs, active_query.cursor)
    page_items = paged_jobs[: active_query.limit]
    next_cursor = None
    if len(paged_jobs) > len(page_items) and page_items:
        next_cursor = str(page_items[-1]["id"])

    return JobListPage(
        items=[
            build_job_summary(record, normalize_summary=True)
            for record in page_items
        ],
        next_cursor=next_cursor,
    )


def get_job_detail(
    jobs: JobHistoryRepository,
    job_id: str,
    *,
    job_items: JobItemsHistoryRepository | None = None,
    events: JobEventsHistoryRepository | None = None,
    settings_audit: SettingsAuditHistoryRepository | None = None,
) -> JobDetail | None:
    """Return a typed job detail snapshot for a single job."""
    job_record = jobs.get(job_id)
    if job_record is None:
        return None

    item_records = job_items.list_for_job(job_id) if job_items is not None else ()
    event_records = events.list_for_job(job_id) if events is not None else ()
    audit_records: Sequence[Mapping[str, Any]] = ()
    if settings_audit is not None:
        audit_records = [
            record
            for record in settings_audit.list_entries()
            if str(record.get("job_id")) == job_id
        ]

    return build_job_detail(job_record, item_records, event_records, audit_records)


def get_settings_view(
    *,
    config: JavsConfig,
    source_path: str,
    config_version: int,
    settings_audit: Sequence[Mapping[str, Any]] = (),
) -> SettingsView:
    """Return a typed settings snapshot for read-side consumers."""
    return SettingsView(
        config=config,
        source_path=source_path,
        config_version=config_version,
        settings_audit=[build_settings_audit_entry(record) for record in settings_audit],
    )


__all__ = [
    "JobDetail",
    "JobEventSummary",
    "JobEventsHistoryRepository",
    "JobHistoryRepository",
    "JobItemSummary",
    "JobItemsHistoryRepository",
    "JobListPage",
    "JobListQuery",
    "JobSummary",
    "JobSummaryPayload",
    "RealtimeEvent",
    "SettingsAuditEntry",
    "SettingsAuditHistoryRepository",
    "SettingsView",
    "build_job_detail",
    "build_job_event_summary",
    "build_job_item_summary",
    "build_job_summary",
    "build_realtime_event",
    "build_settings_audit_entry",
    "get_job_detail",
    "get_settings_view",
    "list_jobs",
    "normalize_job_summary_payload",
]
