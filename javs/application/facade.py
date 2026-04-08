"""Shared application facade surface for CLI and future API adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from javs.application.models import (
    FindMovieRequest,
    FindMovieResponse,
    JobDetail,
    JobStartResponse,
    JobSummary,
    SaveSettingsRequest,
    SaveSettingsResponse,
    SettingsResponse,
    SortJobRequest,
    UpdateJobRequest,
)
from javs.config import JavsConfig, load_config, save_config


class PlatformFacade:
    """Main application entrypoint shared by CLI and future API adapters."""

    def __init__(
        self,
        *,
        jobs: Any,
        job_items: Any = None,
        events: Any = None,
        settings_audit: Any = None,
        history: Any = None,
        runner: Any = None,
        config_loader: Callable[[Path], JavsConfig] = load_config,
        config_saver: Callable[[JavsConfig, Path], None] = save_config,
    ) -> None:
        self.jobs = jobs
        self.job_items = job_items
        self.events = events
        self.settings_audit = settings_audit
        self.history = history
        self.runner = runner
        self.config_loader = config_loader
        self.config_saver = config_saver

    async def find_movie(
        self,
        request: FindMovieRequest,
        *,
        origin: str = "cli",
    ) -> FindMovieResponse:
        """Run a shared find flow once a runner-backed implementation exists."""
        raise NotImplementedError("PlatformFacade.find_movie is implemented in a later task.")

    async def start_sort_job(
        self,
        request: SortJobRequest,
        *,
        origin: str = "cli",
    ) -> JobStartResponse:
        """Start a shared sort job once the job runner exists."""
        raise NotImplementedError("PlatformFacade.start_sort_job is implemented in a later task.")

    async def start_update_job(
        self,
        request: UpdateJobRequest,
        *,
        origin: str = "cli",
    ) -> JobStartResponse:
        """Start a shared update job once the job runner exists."""
        raise NotImplementedError("PlatformFacade.start_update_job is implemented in a later task.")

    def get_job(self, job_id: str) -> JobDetail | None:
        """Return job detail once history reads are wired through the facade."""
        raise NotImplementedError("PlatformFacade.get_job is implemented in a later task.")

    def list_jobs(self, *, limit: int | None = None) -> list[JobSummary]:
        """Return job summaries once history reads are wired through the facade."""
        raise NotImplementedError("PlatformFacade.list_jobs is implemented in a later task.")

    def get_settings(self, source_path: Path) -> SettingsResponse:
        """Return active settings once the shared settings flow is implemented."""
        raise NotImplementedError("PlatformFacade.get_settings is implemented in a later task.")

    def save_settings(
        self,
        request: SaveSettingsRequest,
        *,
        origin: str = "cli",
    ) -> SaveSettingsResponse:
        """Persist settings once the shared settings flow is implemented."""
        raise NotImplementedError("PlatformFacade.save_settings is implemented in a later task.")
