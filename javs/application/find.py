"""Shared application-layer use case for short-running find jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from javs.application.history import JobHistoryRepository, build_job_summary
from javs.application.models import FindMovieRequest, FindMovieResponse
from javs.jobs.executor import JobExecutionContext, JobExecutionResult, JobExecutor

_FIND_TERMINAL_STATUSES = frozenset({"completed", "failed"})


@dataclass(slots=True)
class FindMovieError(Exception):
    """Structured application error for failed or incompatible find execution."""

    job_id: str
    error: dict[str, Any]

    def __str__(self) -> str:
        error_type = self.error.get("type", "FindMovieError")
        message = self.error.get("message", "Find job failed.")
        return f"{error_type} for job {self.job_id}: {message}"


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
    """Runner surface for synchronous, short-running find execution."""

    async def run_find(
        self,
        request: FindMovieRequest,
        *,
        origin: str,
        executor: JobExecutor[FindMovieRequest] | None = None,
    ) -> str:
        """Persist and execute a find job, returning only after a terminal job row exists."""


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
        """Run the shared find flow through the synchronous in-process runner path."""
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

        job_record = self._require_terminal_job(job_id)

        error = job_record.get("error_json")
        if job_record.get("status") == "failed":
            raise FindMovieError(
                job_id=job_id,
                error=self._normalize_error_payload(
                    error,
                    fallback_type="FindJobFailed",
                    fallback_message="Find job failed.",
                ),
            )

        return FindMovieResponse(
            job=build_job_summary(job_record),
            result=result,
        )

    def _require_terminal_job(self, job_id: str) -> dict[str, Any]:
        """Ensure the synchronous find runner returned only after persisting a terminal job row."""
        job_record = self.jobs.get(job_id)
        if job_record is None:
            raise FindMovieError(
                job_id=job_id,
                error={
                    "type": "FindContractError",
                    "message": (
                        "Find requires a terminal job row to be persisted before the runner "
                        "returns."
                    ),
                    "status": "missing",
                },
            )

        status = str(job_record.get("status", "unknown"))
        if status not in _FIND_TERMINAL_STATUSES:
            raise FindMovieError(
                job_id=job_id,
                error={
                    "type": "FindContractError",
                    "message": (
                        "Find requires a terminal job row to be persisted before the runner "
                        "returns."
                    ),
                    "status": status,
                },
            )
        return job_record

    def _normalize_error_payload(
        self,
        error: object,
        *,
        fallback_type: str,
        fallback_message: str,
    ) -> dict[str, Any]:
        """Return a structured error payload for callers."""
        if isinstance(error, dict):
            payload = dict(error)
            payload.setdefault("type", fallback_type)
            payload.setdefault("message", fallback_message)
            return payload
        return {
            "type": fallback_type,
            "message": fallback_message,
        }
