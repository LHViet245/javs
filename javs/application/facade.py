"""Shared application facade surface for CLI and future API adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from javs.application.history import JobHistoryRepository, JobItemsHistoryRepository
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
from javs.jobs.executor import JobExecutor


class JobEventsRepository(Protocol):
    """Minimal event repository contract kept for future facade wiring."""

    def list_for_job(self, job_id: str) -> list[dict[str, object]]:
        """Return persisted events for a job."""


class SettingsAuditRepository(Protocol):
    """Minimal settings audit repository contract kept for future facade wiring."""

    def list_entries(self) -> list[dict[str, object]]:
        """Return persisted settings audit rows."""


class PlatformHistory(Protocol):
    """Minimal history service contract exposed to the facade."""

    def get_job(self, job_id: str) -> JobDetail | None:
        """Return a mapped job detail for a single job."""

    def list_jobs(self, *, limit: int | None = None) -> list[JobSummary]:
        """Return mapped job summaries."""


class PlatformRunner(Protocol):
    """Minimal runner contract reserved for later task wiring."""

    async def run_job(
        self,
        *,
        kind: str,
        origin: str,
        request: object | None,
        executor: JobExecutor[object | None],
    ) -> str:
        """Create and execute a job with a supplied executor."""

    async def run_find(
        self,
        request: FindMovieRequest,
        *,
        origin: str,
        executor: JobExecutor[FindMovieRequest] | None = None,
    ) -> str:
        """Create and execute a find job, returning its job ID."""

    async def run_sort(
        self,
        request: SortJobRequest,
        *,
        origin: str,
        executor: JobExecutor[SortJobRequest] | None = None,
    ) -> str:
        """Create and execute a sort job, returning its job ID."""

    async def run_update(
        self,
        request: UpdateJobRequest,
        *,
        origin: str,
        executor: JobExecutor[UpdateJobRequest] | None = None,
    ) -> str:
        """Create and execute an update job, returning its job ID."""


ConfigLoader = Callable[[Path], JavsConfig]
ConfigSaver = Callable[[JavsConfig, Path], None]


class PlatformFacade:
    """Main application entrypoint shared by CLI and future API adapters."""

    def __init__(
        self,
        *,
        jobs: JobHistoryRepository,
        job_items: JobItemsHistoryRepository | None = None,
        events: JobEventsRepository | None = None,
        settings_audit: SettingsAuditRepository | None = None,
        history: PlatformHistory | None = None,
        runner: PlatformRunner | None = None,
        config_loader: ConfigLoader = load_config,
        config_saver: ConfigSaver = save_config,
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
