"""Thin route helpers for job endpoints."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from javs.application import (
    FindMovieRequest,
    FindMovieResponse,
    JobDetail,
    JobEventSummary,
    JobListPage,
    JobListQuery,
    RealtimeEvent,
    SortJobRequest,
    UpdateJobRequest,
)
from javs.jobs.events import RealtimeEvent as HubRealtimeEvent


async def handle_find_job(facade, payload: Mapping[str, Any]) -> FindMovieResponse:
    """Run a find request through the shared facade."""
    request = FindMovieRequest.model_validate(dict(payload))
    return await facade.find_movie(request, origin="api")


async def handle_sort_job(facade, payload: Mapping[str, Any]):
    """Run a sort request through the shared facade."""
    request = SortJobRequest.model_validate(dict(payload))
    return await facade.start_sort_job(request, origin="api")


async def handle_update_job(facade, payload: Mapping[str, Any]):
    """Run an update request through the shared facade."""
    request = UpdateJobRequest.model_validate(dict(payload))
    return await facade.start_update_job(request, origin="api")


def handle_list_jobs(facade, query_params: Mapping[str, Any] | None = None) -> JobListPage:
    """Return a typed job page through the shared facade."""
    query = JobListQuery.model_validate(dict(query_params or {}))
    return facade.list_jobs(query)


def handle_get_job(facade, job_id: str) -> JobDetail | None:
    """Return a typed job detail through the shared facade."""
    return facade.get_job(job_id)


def build_realtime_event(event: HubRealtimeEvent) -> RealtimeEvent:
    """Adapt a hub event into the shared realtime response model."""
    return RealtimeEvent(
        type=event.event_type,
        job_id=event.job_id,
        event=JobEventSummary(
            id=event.id,
            job_id=event.job_id,
            event_type=event.event_type,
            job_item_id=event.job_item_id,
            payload=event.payload,
            created_at=None,
        ),
    )


def serialize_realtime_event(event: RealtimeEvent) -> str:
    """Serialize the shared realtime event model for transport."""
    return json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
