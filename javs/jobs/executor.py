"""Generic executor contracts and helpers for platform jobs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Protocol, TypeAlias, TypeVar

from pydantic import BaseModel

RequestT = TypeVar("RequestT")


class JobEventWriter(Protocol):
    """Write executor-originated events for a specific job."""

    def emit(
        self,
        event_type: str,
        *,
        payload: object | None = None,
        job_item_id: int | None = None,
    ) -> int:
        """Persist an event for the active job."""


@dataclass(slots=True)
class JobExecutionContext(Generic[RequestT]):
    """Context passed to async job executors."""

    job_id: str
    kind: str
    origin: str
    request: RequestT | None
    events: JobEventWriter


@dataclass(slots=True)
class JobExecutionResult:
    """Stored result payloads produced by a completed job."""

    result: object | None = None
    summary: object | None = None


JobExecutor: TypeAlias = Callable[
    [JobExecutionContext[RequestT]],
    Awaitable[JobExecutionResult | object | None],
]


def serialize_job_value(value: object) -> Any:
    """Convert common application values into JSON-friendly data."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, BaseModel):
        return serialize_job_value(value.model_dump(mode="json"))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): serialize_job_value(item) for key, item in value.items()}
    if isinstance(value, set | frozenset):
        return [serialize_job_value(item) for item in value]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [serialize_job_value(item) for item in value]
    raise TypeError(f"Unsupported job payload type: {value.__class__.__name__}")


def normalize_execution_result(value: JobExecutionResult | object | None) -> JobExecutionResult:
    """Normalize executor return values into a stored result envelope."""
    if isinstance(value, JobExecutionResult):
        return JobExecutionResult(
            result=serialize_job_value(value.result),
            summary=serialize_job_value(value.summary),
        )
    return JobExecutionResult(result=serialize_job_value(value))


def build_failure_details(error: Exception) -> dict[str, str]:
    """Return a small, stable error payload for failed jobs."""
    return {
        "type": error.__class__.__name__,
        "message": str(error),
    }
