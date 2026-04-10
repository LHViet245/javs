"""Thin route helpers for job endpoints."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from javs.application import (
    FindMovieRequest,
    FindMovieResponse,
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
