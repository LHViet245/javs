"""Shared application-layer use case for short-running find jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from javs.application.history import JobHistoryRepository, build_job_summary
from javs.application.models import FindMovieRequest, FindMovieResponse
from javs.jobs.executor import JobExecutionContext, JobExecutionResult, JobExecutor


class FindMovieEngine(Protocol):
    """Minimal engine surface needed by the shared find use case."""

    async def find_one(
        self,
        movie_id: str,
        scraper_names: list[str] | None = None,
        aggregate: bool = True,
    ):
        """Return metadata for a single movie ID with managed session lifecycle."""

    def get_last_run_diagnostics(self) -> list[dict[str, str]]:
        """Return a snapshot of diagnostics collected during the last find run."""


FindMovieEngineFactory = Callable[[], FindMovieEngine]


class FindMovieRunner(Protocol):
    """Minimal runner surface used by the shared find use case."""

    async def run_find(
        self,
        request: FindMovieRequest,
        *,
        origin: str,
        executor: JobExecutor[FindMovieRequest] | None = None,
    ) -> str:
        """Persist and execute a find job, returning its job ID."""


@dataclass(slots=True)
class FindMovieUseCase:
    """Create a persisted find job and return the completed shared response."""

    jobs: JobHistoryRepository
    runner: FindMovieRunner
    engine_factory: FindMovieEngineFactory
    last_run_diagnostics: list[dict[str, str]] = field(default_factory=list)

    async def run(
        self,
        request: FindMovieRequest,
        *,
        origin: str = "cli",
    ) -> FindMovieResponse:
        """Run the shared find flow through the platform runner."""
        self.last_run_diagnostics = []
        engine = self.engine_factory()
        result = None

        async def execute_find(
            context: JobExecutionContext[FindMovieRequest],
        ) -> JobExecutionResult:
            nonlocal result
            active_request = context.request or request
            result = await engine.find_one(
                active_request.movie_id,
                scraper_names=active_request.scraper_names,
            )
            return JobExecutionResult(
                result=result,
                summary={"matched": int(result is not None)},
            )

        job_id = await self.runner.run_find(
            request,
            origin=origin,
            executor=execute_find,
        )
        self.last_run_diagnostics = engine.get_last_run_diagnostics()

        job_record = self.jobs.get(job_id)
        if job_record is None:
            raise RuntimeError(f"Find job {job_id} was not persisted.")

        error = job_record.get("error_json")
        if job_record.get("status") == "failed" and isinstance(error, dict):
            raise RuntimeError(str(error.get("message", "Find job failed.")))

        return FindMovieResponse(
            job=build_job_summary(job_record),
            result=result,
        )
