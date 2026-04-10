"""Shared application facade surface for CLI and future API adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from javs.application.find import FindMovieEngineFactory, FindMovieUseCase
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
from javs.application.settings import SettingsUseCase
from javs.application.sort_jobs import SortEngineFactory, SortJobUseCase
from javs.application.update_jobs import UpdateEngineFactory, UpdateJobUseCase
from javs.config import JavsConfig, load_config, save_config
from javs.jobs.executor import JobExecutor


class JobEventsRepository(Protocol):
    """Minimal event repository contract kept for future facade wiring."""

    def list_for_job(self, job_id: str) -> list[dict[str, object]]:
        """Return persisted events for a job."""


class SettingsAuditRepository(Protocol):
    """Minimal settings audit repository contract kept for future facade wiring."""

    def create_entry(
        self,
        *,
        job_id: str,
        source_path: str,
        config_version: int,
        before_json: object | None = None,
        after_json: object | None = None,
        change_summary_json: object | None = None,
    ) -> int:
        """Persist a settings audit row."""

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
        """Create and execute a short-running find job, returning after terminal persistence."""

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
        find_engine_factory: FindMovieEngineFactory | None = None,
        sort_engine_factory: SortEngineFactory | None = None,
        update_engine_factory: UpdateEngineFactory | None = None,
        config_loader: ConfigLoader = load_config,
        config_saver: ConfigSaver = save_config,
    ) -> None:
        self.jobs = jobs
        self.job_items = job_items
        self.events = events
        self.settings_audit = settings_audit
        self.history = history
        self.runner = runner
        self.find_engine_factory = find_engine_factory
        self.sort_engine_factory = sort_engine_factory
        self.update_engine_factory = update_engine_factory
        self.config_loader = config_loader
        self.config_saver = config_saver
        self.last_run_diagnostics: list[dict[str, str]] = []
        self.last_run_items: list[dict[str, object]] = []
        self.last_preview_plan: list[dict[str, str]] = []
        self.last_run_results: list[object] = []
        self.last_run_summary: dict[str, int] = {}

    async def find_movie(
        self,
        request: FindMovieRequest,
        *,
        origin: str = "cli",
    ) -> FindMovieResponse:
        """Run the synchronous shared find flow through the platform job runner."""
        if self.runner is None or self.find_engine_factory is None:
            raise NotImplementedError(
                "PlatformFacade.find_movie requires a runner and find_engine_factory."
            )

        use_case = FindMovieUseCase(
            jobs=self.jobs,
            runner=self.runner,
            engine_factory=self.find_engine_factory,
        )
        try:
            return await use_case.run(request, origin=origin)
        finally:
            self.last_run_diagnostics = use_case.last_run_diagnostics

    async def start_sort_job(
        self,
        request: SortJobRequest,
        *,
        origin: str = "cli",
    ) -> JobStartResponse:
        """Run the synchronous shared sort flow through the platform job runner."""
        if self.runner is None:
            raise NotImplementedError("PlatformFacade.start_sort_job requires a runner.")

        engine_factory = self.sort_engine_factory or self.find_engine_factory
        if engine_factory is None:
            raise NotImplementedError("PlatformFacade.start_sort_job requires an engine factory.")

        use_case = SortJobUseCase(
            jobs=self.jobs,
            job_items=self.job_items,
            runner=self.runner,
            engine_factory=engine_factory,
        )
        response = await use_case.run(request, origin=origin)
        self._capture_batch_state(use_case)
        return response

    async def start_update_job(
        self,
        request: UpdateJobRequest,
        *,
        origin: str = "cli",
    ) -> JobStartResponse:
        """Run the synchronous shared update flow through the platform job runner."""
        if self.runner is None:
            raise NotImplementedError("PlatformFacade.start_update_job requires a runner.")

        engine_factory = self.update_engine_factory or self.find_engine_factory
        if engine_factory is None:
            raise NotImplementedError("PlatformFacade.start_update_job requires an engine factory.")

        use_case = UpdateJobUseCase(
            jobs=self.jobs,
            job_items=self.job_items,
            runner=self.runner,
            engine_factory=engine_factory,
        )
        response = await use_case.run(request, origin=origin)
        self._capture_batch_state(use_case)
        return response

    def get_job(self, job_id: str) -> JobDetail | None:
        """Return job detail once history reads are wired through the facade."""
        raise NotImplementedError("PlatformFacade.get_job is implemented in a later task.")

    def list_jobs(self, *, limit: int | None = None) -> list[JobSummary]:
        """Return job summaries once history reads are wired through the facade."""
        raise NotImplementedError("PlatformFacade.list_jobs is implemented in a later task.")

    def get_settings(self, source_path: Path) -> SettingsResponse:
        """Return active settings through the shared application use case."""
        return SettingsUseCase(
            jobs=self.jobs,
            config_loader=self.config_loader,
            config_saver=self.config_saver,
        ).get(source_path)

    async def save_settings(
        self,
        request: SaveSettingsRequest,
        *,
        origin: str = "cli",
    ) -> SaveSettingsResponse:
        """Persist settings through the shared application use case."""
        return await SettingsUseCase(
            jobs=self.jobs,
            config_loader=self.config_loader,
            config_saver=self.config_saver,
            runner=self.runner,
            settings_audit=self.settings_audit,
        ).save(request, origin=origin)

    def _capture_batch_state(self, use_case: SortJobUseCase | UpdateJobUseCase) -> None:
        self.last_run_diagnostics = [dict(item) for item in use_case.last_run_diagnostics]
        self.last_run_items = [dict(item) for item in use_case.last_run_items]
        self.last_preview_plan = [dict(item) for item in use_case.last_preview_plan]
        self.last_run_results = list(use_case.last_run_results)
        self.last_run_summary = dict(use_case.last_run_summary)
