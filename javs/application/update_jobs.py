"""Shared application-layer use case for persisted update jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from javs.application.history import JobHistoryRepository, build_job_summary
from javs.application.models import BatchJobError, JobStartResponse, UpdateJobRequest
from javs.jobs.executor import JobExecutionContext, JobExecutionResult, JobExecutor

_TERMINAL_JOB_STATUSES = frozenset({"completed", "failed"})


class UpdateEngine(Protocol):
    """Minimal engine surface needed by the shared update use case."""

    last_preview_plan: list[dict[str, str]]
    last_run_diagnostics: list[dict[str, str]]
    last_run_items: list[dict[str, object]]
    last_run_summary: dict[str, int]

    async def update_path(
        self,
        source: Path,
        recurse: bool = False,
        force: bool = False,
        preview: bool = False,
        scraper_names: list[str] | None = None,
        refresh_images: bool = False,
        refresh_trailer: bool = False,
    ):
        """Refresh metadata for a batch of sorted files."""


UpdateEngineFactory = Callable[[], UpdateEngine]


class UpdateRunner(Protocol):
    """Runner surface for synchronous, in-process update execution."""

    async def run_update(
        self,
        request: UpdateJobRequest,
        *,
        origin: str,
        executor: JobExecutor[UpdateJobRequest] | None = None,
    ) -> str:
        """Persist and execute an update job, returning only after terminal persistence."""


class JobItemsWriter(Protocol):
    """Persist item-level history rows for batch jobs."""

    def create_item(
        self,
        *,
        job_id: str,
        item_key: str,
        status: str,
        source_path: str | None = None,
        dest_path: str | None = None,
        movie_id: str | None = None,
        step: str | None = None,
        message: str | None = None,
        metadata_json: object | None = None,
        error_json: object | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> int:
        """Insert a job item row and return its identifier."""


@dataclass(slots=True)
class UpdateJobUseCase:
    """Create a persisted update job and expose the completed shared response state."""

    jobs: JobHistoryRepository
    runner: UpdateRunner
    engine_factory: UpdateEngineFactory
    job_items: JobItemsWriter | None = None
    last_preview_plan: list[dict[str, str]] = field(default_factory=list)
    last_run_diagnostics: list[dict[str, str]] = field(default_factory=list)
    last_run_items: list[dict[str, object]] = field(default_factory=list)
    last_run_results: list[object] = field(default_factory=list)
    last_run_summary: dict[str, int] = field(default_factory=dict)

    async def run(
        self,
        request: UpdateJobRequest,
        *,
        origin: str = "cli",
    ) -> JobStartResponse:
        """Run the shared update flow through the synchronous in-process runner path."""
        self._reset_last_run_state()
        engine = self.engine_factory()

        async def execute_update(
            context: JobExecutionContext[UpdateJobRequest],
        ) -> JobExecutionResult:
            active_request = context.request or request
            results: list[object] = []
            try:
                results = await engine.update_path(
                    Path(active_request.source_path),
                    recurse=active_request.recurse,
                    force=active_request.force,
                    preview=active_request.preview,
                    scraper_names=active_request.scraper_names,
                    refresh_images=active_request.refresh_images,
                    refresh_trailer=active_request.refresh_trailer,
                )
            finally:
                self._capture_engine_state(engine, results)
                self._persist_items(context.job_id, context)
            return JobExecutionResult(result=results, summary=self.last_run_summary)

        job_id = await self.runner.run_update(
            request,
            origin=origin,
            executor=execute_update,
        )
        job_record = self._require_completed_job(job_id)
        return JobStartResponse(job=build_job_summary(job_record))

    def _capture_engine_state(self, engine: UpdateEngine, results: list[object]) -> None:
        self.last_run_results = list(results)
        self.last_run_summary = dict(getattr(engine, "last_run_summary", {}))
        self.last_run_diagnostics = [
            dict(item) for item in getattr(engine, "last_run_diagnostics", [])
        ]
        self.last_preview_plan = [dict(item) for item in getattr(engine, "last_preview_plan", [])]
        self.last_run_items = [dict(item) for item in getattr(engine, "last_run_items", [])]

    def _persist_items(
        self,
        job_id: str,
        context: JobExecutionContext[UpdateJobRequest],
    ) -> None:
        if self.job_items is None:
            return

        for index, item in enumerate(self.last_run_items, start=1):
            item_key = str(item.get("item_key") or item.get("movie_id") or f"item-{index}")
            item_id = self.job_items.create_item(
                job_id=job_id,
                item_key=item_key,
                status=str(item.get("status", "completed")),
                source_path=_string_or_none(item.get("source_path")),
                dest_path=_string_or_none(item.get("dest_path")),
                movie_id=_string_or_none(item.get("movie_id")),
                step=_string_or_none(item.get("step")),
                message=_string_or_none(item.get("message")),
                metadata_json=item.get("metadata"),
                error_json=item.get("error"),
            )
            context.events.emit(
                "job.item.recorded",
                job_item_id=item_id,
                payload={"item_key": item_key, "status": item.get("status", "completed")},
            )

    def _reset_last_run_state(self) -> None:
        self.last_preview_plan = []
        self.last_run_diagnostics = []
        self.last_run_items = []
        self.last_run_results = []
        self.last_run_summary = {}

    def _require_completed_job(self, job_id: str) -> dict[str, Any]:
        job_record = self.jobs.get(job_id)
        if job_record is None:
            raise BatchJobError(
                job_id=job_id,
                kind="update",
                error={
                    "type": "BatchJobContractError",
                    "message": (
                        "Update requires a terminal job row to be persisted before the runner "
                        "returns."
                    ),
                    "status": "missing",
                },
            )

        status = str(job_record.get("status", "unknown"))
        if status == "failed":
            raise BatchJobError(
                job_id=job_id,
                kind="update",
                error=self._normalize_error_payload(
                    job_record.get("error_json"),
                    fallback_type="UpdateJobFailed",
                    fallback_message="Update job failed.",
                ),
            )
        if status not in _TERMINAL_JOB_STATUSES:
            raise BatchJobError(
                job_id=job_id,
                kind="update",
                error={
                    "type": "BatchJobContractError",
                    "message": (
                        "Update requires a terminal job row to be persisted before the runner "
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
        if isinstance(error, dict):
            payload = dict(error)
            payload.setdefault("type", fallback_type)
            payload.setdefault("message", fallback_message)
            return payload
        return {
            "type": fallback_type,
            "message": fallback_message,
        }


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
