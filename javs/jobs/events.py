"""Event helpers for job lifecycle persistence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from javs.jobs.executor import serialize_job_value


@dataclass(slots=True, frozen=True)
class RealtimeEvent:
    """In-process event published after a job event is stored."""

    id: int
    job_id: str
    event_type: str
    job_item_id: int | None
    payload: object | None


class EventHub:
    """Shared in-process hub for realtime job event fanout."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[RealtimeEvent]] = []

    def subscribe(self) -> asyncio.Queue[RealtimeEvent]:
        """Register a queue that receives live events in publish order."""
        queue: asyncio.Queue[RealtimeEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RealtimeEvent]) -> None:
        """Remove a previously subscribed queue from the hub."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def close(self, queue: asyncio.Queue[RealtimeEvent]) -> None:
        """Alias for unsubscribe to support explicit subscriber teardown."""
        self.unsubscribe(queue)

    def publish_nowait(self, event: RealtimeEvent) -> None:
        """Fan out an event to all current subscribers without awaiting."""
        for queue in list(self._subscribers):
            queue.put_nowait(event)


class JobEventRepository(Protocol):
    """Minimal repository contract for storing job events."""

    def add_event(
        self,
        *,
        job_id: str,
        event_type: str,
        job_item_id: int | None = None,
        payload_json: object | None = None,
    ) -> int:
        """Insert and return a stored event row ID."""


@dataclass(slots=True)
class PlatformJobEvents:
    """Helper bound to a single job for consistent lifecycle events."""

    repository: JobEventRepository
    job_id: str
    hub: EventHub | None = None

    def emit(
        self,
        event_type: str,
        *,
        payload: object | None = None,
        job_item_id: int | None = None,
    ) -> int:
        """Persist a raw event for the active job."""
        event_id = self.repository.add_event(
            job_id=self.job_id,
            job_item_id=job_item_id,
            event_type=event_type,
            payload_json=serialize_job_value(payload),
        )
        if self.hub is not None:
            self.hub.publish_nowait(
                RealtimeEvent(
                    id=event_id,
                    job_id=self.job_id,
                    event_type=event_type,
                    job_item_id=job_item_id,
                    payload=serialize_job_value(payload),
                )
            )
        return event_id

    def emit_job_created(self, *, kind: str, origin: str, request: object | None = None) -> int:
        """Persist the initial job-created event."""
        payload = {"kind": kind, "origin": origin}
        if request is not None:
            payload["request"] = serialize_job_value(request)
        return self.emit("job.created", payload=payload)

    def emit_job_started(self, *, kind: str, origin: str) -> int:
        """Persist the job-started event."""
        return self.emit("job.started", payload={"kind": kind, "origin": origin})

    def emit_job_completed(
        self,
        *,
        result: object | None = None,
        summary: object | None = None,
    ) -> int:
        """Persist the job-completed event."""
        payload: dict[str, object] = {}
        if result is not None:
            payload["result"] = serialize_job_value(result)
        if summary is not None:
            payload["summary"] = serialize_job_value(summary)
        return self.emit("job.completed", payload=payload or None)

    def emit_job_failed(self, *, error: dict[str, str]) -> int:
        """Persist the job-failed event."""
        return self.emit("job.failed", payload=error)

    def emit_job_cancelled(self, *, error: dict[str, str]) -> int:
        """Persist the job-cancelled event."""
        return self.emit("job.cancelled", payload=error)
