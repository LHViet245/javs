"""Thin route helpers for job endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from javs.application import (
    FindMovieRequest,
    FindMovieResponse,
    JobDetail,
    JobListPage,
    JobListQuery,
    SortJobRequest,
    UpdateJobRequest,
)


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
