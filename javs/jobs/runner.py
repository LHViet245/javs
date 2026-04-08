"""In-process platform job runner."""

from __future__ import annotations

from javs.application.models import FindMovieRequest, SortJobRequest, UpdateJobRequest
from javs.database.repositories.events import JobEventsRepository
from javs.database.repositories.jobs import JobsRepository, utc_now
from javs.jobs.events import PlatformJobEvents
from javs.jobs.executor import (
    JobExecutionContext,
    JobExecutor,
    build_failure_details,
    normalize_execution_result,
    serialize_job_value,
)


class PlatformJobRunner:
    """Create jobs, execute them in-process, and persist lifecycle events."""

    def __init__(
        self,
        *,
        jobs: JobsRepository,
        events: JobEventsRepository,
    ) -> None:
        self.jobs = jobs
        self.events = events

    async def run_job(
        self,
        *,
        kind: str,
        origin: str,
        request: object | None,
        executor: JobExecutor[object | None],
    ) -> str:
        """Run a generic job executor and persist the resulting lifecycle."""
        job_id = self.jobs.create_job(
            kind=kind,
            origin=origin,
            request_json=serialize_job_value(request),
        )
        job_events = PlatformJobEvents(repository=self.events, job_id=job_id)
        job_events.emit_job_created(kind=kind, origin=origin, request=request)

        self.jobs.mark_started(job_id)
        job_events.emit_job_started(kind=kind, origin=origin)

        context = JobExecutionContext(
            job_id=job_id,
            kind=kind,
            origin=origin,
            request=request,
            events=job_events,
        )

        try:
            execution = normalize_execution_result(await executor(context))
        except Exception as error:
            failure = build_failure_details(error)
            self.jobs.update_job(
                job_id,
                status="failed",
                error_json=failure,
                finished_at=utc_now(),
            )
            job_events.emit_job_failed(error=failure)
            return job_id

        self.jobs.mark_completed(
            job_id,
            result_json=execution.result,
            summary_json=execution.summary,
        )
        job_events.emit_job_completed(
            result=execution.result,
            summary=execution.summary,
        )
        return job_id

    async def run_find(
        self,
        request: FindMovieRequest,
        *,
        origin: str,
        executor: JobExecutor[FindMovieRequest] | None = None,
    ) -> str:
        """Run a find job once a concrete executor is supplied."""
        return await self._run_typed_job(
            kind="find",
            origin=origin,
            request=request,
            executor=executor,
        )

    async def run_sort(
        self,
        request: SortJobRequest,
        *,
        origin: str,
        executor: JobExecutor[SortJobRequest] | None = None,
    ) -> str:
        """Run a sort job once a concrete executor is supplied."""
        return await self._run_typed_job(
            kind="sort",
            origin=origin,
            request=request,
            executor=executor,
        )

    async def run_update(
        self,
        request: UpdateJobRequest,
        *,
        origin: str,
        executor: JobExecutor[UpdateJobRequest] | None = None,
    ) -> str:
        """Run an update job once a concrete executor is supplied."""
        return await self._run_typed_job(
            kind="update",
            origin=origin,
            request=request,
            executor=executor,
        )

    async def _run_typed_job(
        self,
        *,
        kind: str,
        origin: str,
        request: FindMovieRequest | SortJobRequest | UpdateJobRequest,
        executor: JobExecutor[FindMovieRequest | SortJobRequest | UpdateJobRequest] | None,
    ) -> str:
        """Dispatch a typed job wrapper through the generic execution path."""
        if executor is None:
            raise NotImplementedError(
                f"PlatformJobRunner.{kind} execution is wired in a later task."
            )
        return await self.run_job(
            kind=kind,
            origin=origin,
            request=request,
            executor=executor,
        )
