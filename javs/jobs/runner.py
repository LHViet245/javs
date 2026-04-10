"""In-process platform job runner."""

from __future__ import annotations

import asyncio

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
        self.connection = jobs.connection

        if events.connection is not self.connection:
            raise ValueError(
                "PlatformJobRunner requires jobs and events repositories to share a connection."
            )

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
        self.connection.commit()

        context = JobExecutionContext(
            job_id=job_id,
            kind=kind,
            origin=origin,
            request=request,
            events=job_events,
        )

        try:
            execution = normalize_execution_result(await executor(context))
            self.jobs.mark_completed(
                job_id,
                result_json=execution.result,
                summary_json=execution.summary,
            )
            job_events.emit_job_completed(
                result=execution.result,
                summary=execution.summary,
            )
            self.connection.commit()
        except asyncio.CancelledError:
            self._mark_cancelled(job_id, job_events)
            raise
        except Exception as error:
            self._mark_failed(job_id, job_events, error)
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

    def _mark_failed(
        self,
        job_id: str,
        job_events: PlatformJobEvents,
        error: Exception,
    ) -> None:
        """Persist a failed terminal state for executor or serialization errors."""
        failure = build_failure_details(error)
        self.jobs.update_job(
            job_id,
            status="failed",
            result_json=None,
            summary_json=None,
            error_json=failure,
            finished_at=utc_now(),
        )
        job_events.emit_job_failed(error=failure)
        self.connection.commit()

    def _mark_cancelled(
        self,
        job_id: str,
        job_events: PlatformJobEvents,
    ) -> None:
        """Persist a failed terminal state for cancelled job execution."""
        cancellation = {
            "type": "CancelledError",
            "message": "Job execution cancelled",
        }
        self.jobs.update_job(
            job_id,
            status="failed",
            result_json=None,
            summary_json=None,
            error_json=cancellation,
            finished_at=utc_now(),
        )
        job_events.emit_job_cancelled(error=cancellation)
        self.connection.commit()
