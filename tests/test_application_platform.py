"""Tests for shared platform application contracts."""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

import pytest

from javs.application import (
    FindMovieRequest,
    JobDetail,
    JobItemSummary,
    JobSummary,
    PlatformFacade,
    SettingsResponse,
    build_job_detail,
    build_job_item_summary,
    build_job_summary,
)
from javs.config import JavsConfig


def test_find_movie_request_normalizes_movie_id_and_scraper_names() -> None:
    request = FindMovieRequest(
        movie_id=" abp420 ",
        scraper_names=[" JavLibrary ", "DMM", "javlibrary", ""],
    )

    assert request.movie_id == "ABP-420"
    assert request.scraper_names == ["javlibrary", "dmm"]


def test_find_movie_request_leaves_malformed_movie_id_unrewritten() -> None:
    request = FindMovieRequest(movie_id=" abp420x ")

    assert request.movie_id == "ABP420X"


def test_job_summary_and_settings_response_expose_expected_fields() -> None:
    job = JobSummary(
        id="job-1",
        kind="find",
        status="pending",
        origin="cli",
        created_at="2026-04-08T00:00:00Z",
        summary={"matched": 1},
    )
    settings = SettingsResponse(
        config=JavsConfig(),
        source_path="/tmp/config.yaml",
        config_version=1,
    )

    assert job.status == "pending"
    assert job.summary == {"matched": 1}
    assert settings.source_path == "/tmp/config.yaml"
    assert settings.config_version == 1
    assert settings.config.database.path == "~/.javs/platform.db"


def test_history_helpers_map_repository_records_to_contract_models() -> None:
    job_record = {
        "id": "job-1",
        "kind": "sort",
        "status": "completed",
        "origin": "cli",
        "created_at": "2026-04-08T00:00:00Z",
        "started_at": "2026-04-08T00:01:00Z",
        "finished_at": "2026-04-08T00:02:00Z",
        "summary_json": {"processed": 2},
        "result_json": {"destination": "/library/sorted"},
        "error_json": None,
    }
    item_record = {
        "id": 7,
        "job_id": "job-1",
        "item_key": "item-1",
        "source_path": "/library/incoming/ABP-420.mp4",
        "dest_path": "/library/sorted/ABP-420.mp4",
        "movie_id": "ABP-420",
        "status": "completed",
        "step": "move",
        "message": "Moved successfully",
        "metadata_json": {"index": 1},
        "error_json": None,
        "created_at": "2026-04-08T00:00:10Z",
        "started_at": "2026-04-08T00:01:10Z",
        "finished_at": "2026-04-08T00:01:20Z",
    }

    summary = build_job_summary(job_record)
    item_summary = build_job_item_summary(item_record)
    detail = build_job_detail(job_record, [item_record])

    assert summary == JobSummary(
        id="job-1",
        kind="sort",
        status="completed",
        origin="cli",
        created_at="2026-04-08T00:00:00Z",
        started_at="2026-04-08T00:01:00Z",
        finished_at="2026-04-08T00:02:00Z",
        summary={"processed": 2},
        error=None,
    )
    assert item_summary == JobItemSummary(
        id=7,
        item_key="item-1",
        status="completed",
        source_path="/library/incoming/ABP-420.mp4",
        dest_path="/library/sorted/ABP-420.mp4",
        movie_id="ABP-420",
        step="move",
        message="Moved successfully",
        metadata={"index": 1},
        error=None,
        created_at="2026-04-08T00:00:10Z",
        started_at="2026-04-08T00:01:10Z",
        finished_at="2026-04-08T00:01:20Z",
    )
    assert detail == JobDetail(
        job=summary,
        result={"destination": "/library/sorted"},
        items=[item_summary],
    )


class StubJobsRepository:
    def get(self, job_id: str) -> dict[str, object] | None:
        return {"id": job_id}

    def list_jobs(self, *, limit: int | None = None) -> list[dict[str, object]]:
        return []


class StubJobItemsRepository:
    def list_for_job(self, job_id: str) -> list[dict[str, object]]:
        return []


class StubJobEventsRepository:
    def list_for_job(self, job_id: str) -> list[dict[str, object]]:
        return []


class StubSettingsAuditRepository:
    def list_entries(self) -> list[dict[str, object]]:
        return []


class StubPlatformHistory:
    def get_job(self, job_id: str) -> JobDetail | None:
        return None

    def list_jobs(self, *, limit: int | None = None) -> list[JobSummary]:
        return []


class StubPlatformRunner:
    async def run_find(self, *args: object, **kwargs: object) -> str:
        raise NotImplementedError

    async def run_sort(self, *args: object, **kwargs: object) -> str:
        raise NotImplementedError

    async def run_update(self, *args: object, **kwargs: object) -> str:
        raise NotImplementedError


def load_test_config(path: Path) -> JavsConfig:
    return JavsConfig()


def save_test_config(config: JavsConfig, path: Path) -> None:
    return None


def test_platform_facade_accepts_typed_dependencies_and_exposes_planned_methods() -> None:
    jobs = StubJobsRepository()
    job_items = StubJobItemsRepository()
    events = StubJobEventsRepository()
    settings_audit = StubSettingsAuditRepository()
    history = StubPlatformHistory()
    runner = StubPlatformRunner()

    facade = PlatformFacade(
        jobs=jobs,
        job_items=job_items,
        events=events,
        settings_audit=settings_audit,
        history=history,
        runner=runner,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    assert facade.jobs is jobs
    assert facade.job_items is job_items
    assert facade.events is events
    assert facade.settings_audit is settings_audit
    assert facade.history is history
    assert facade.runner is runner
    assert facade.config_loader is load_test_config
    assert facade.config_saver is save_test_config

    assert inspect.iscoroutinefunction(PlatformFacade.find_movie)
    assert inspect.iscoroutinefunction(PlatformFacade.start_sort_job)
    assert inspect.iscoroutinefunction(PlatformFacade.start_update_job)

    for method_name in [
        "find_movie",
        "start_sort_job",
        "start_update_job",
        "get_job",
        "list_jobs",
        "get_settings",
        "save_settings",
    ]:
        assert hasattr(facade, method_name)


def build_platform_runner(tmp_path: Path):
    from javs.database.connection import open_database
    from javs.database.migrations import initialize_database
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.jobs import PlatformJobRunner

    db_path = tmp_path / "platform.db"
    initialize_database(db_path)
    connection = open_database(db_path)

    return db_path, connection, PlatformJobRunner(
        jobs=JobsRepository(connection),
        events=JobEventsRepository(connection),
    )


def load_persisted_job_state(
    db_path: Path,
    job_id: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    from javs.database.connection import open_database
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository

    with open_database(db_path) as connection:
        jobs = JobsRepository(connection)
        events = JobEventsRepository(connection)
        return jobs.get(job_id), events.list_for_job(job_id)


@pytest.mark.asyncio
async def test_runner_persists_completed_job_and_events_across_connection_reopen(
    tmp_path: Path,
) -> None:
    from javs.jobs import JobExecutionContext, JobExecutionResult

    db_path, connection, runner = build_platform_runner(tmp_path)

    async def successful_executor(
        context: JobExecutionContext[FindMovieRequest],
    ) -> JobExecutionResult:
        assert context.job_id
        assert context.kind == "find"
        assert context.origin == "cli"
        assert context.request.movie_id == "ABP-420"
        return JobExecutionResult(
            result={"movie_id": context.request.movie_id},
            summary={"matched": 1},
        )

    try:
        job_id = await runner.run_job(
            kind="find",
            origin="cli",
            request=FindMovieRequest(movie_id="ABP-420"),
            executor=successful_executor,
        )
    finally:
        connection.close()

    job, events = load_persisted_job_state(db_path, job_id)

    assert job is not None
    assert job["status"] == "completed"
    assert job["started_at"] is not None
    assert job["finished_at"] is not None
    assert job["result_json"] == {"movie_id": "ABP-420"}
    assert job["summary_json"] == {"matched": 1}
    assert [event["event_type"] for event in events] == [
        "job.created",
        "job.started",
        "job.completed",
    ]


@pytest.mark.asyncio
async def test_runner_persists_failed_job_and_events_across_connection_reopen(
    tmp_path: Path,
) -> None:
    from javs.jobs import JobExecutionContext

    db_path, connection, runner = build_platform_runner(tmp_path)

    async def failing_executor(context: JobExecutionContext[dict[str, Any] | None]) -> None:
        assert context.kind == "find"
        raise RuntimeError("boom")

    try:
        job_id = await runner.run_job(
            kind="find",
            origin="cli",
            request={"movie_id": "ABP-420"},
            executor=failing_executor,
        )
    finally:
        connection.close()

    job, events = load_persisted_job_state(db_path, job_id)

    assert job is not None
    assert job["status"] == "failed"
    assert job["finished_at"] is not None
    assert job["error_json"] == {"type": "RuntimeError", "message": "boom"}
    assert [event["event_type"] for event in events] == [
        "job.created",
        "job.started",
        "job.failed",
    ]
    assert events[-1]["payload_json"] == {"type": "RuntimeError", "message": "boom"}


@pytest.mark.asyncio
async def test_runner_marks_job_failed_when_executor_returns_unsupported_result_value(
    tmp_path: Path,
) -> None:
    from javs.jobs import JobExecutionContext, JobExecutionResult

    db_path, connection, runner = build_platform_runner(tmp_path)

    async def unsupported_result_executor(
        context: JobExecutionContext[FindMovieRequest],
    ) -> JobExecutionResult:
        assert context.request is not None
        return JobExecutionResult(result={"movie_id": object()})

    try:
        job_id = await runner.run_job(
            kind="find",
            origin="cli",
            request=FindMovieRequest(movie_id="ABP-420"),
            executor=unsupported_result_executor,
        )
    finally:
        connection.close()

    job, events = load_persisted_job_state(db_path, job_id)

    assert job is not None
    assert job["status"] == "failed"
    assert job["finished_at"] is not None
    assert job["error_json"] is not None
    assert job["error_json"]["type"] == "TypeError"
    assert "Unsupported job payload type" in job["error_json"]["message"]
    assert [event["event_type"] for event in events] == [
        "job.created",
        "job.started",
        "job.failed",
    ]
    assert events[-1]["payload_json"] is not None
    assert events[-1]["payload_json"]["type"] == "TypeError"


@pytest.mark.asyncio
async def test_runner_persists_cancelled_job_and_emits_cancellation_event(
    tmp_path: Path,
) -> None:
    from javs.jobs import JobExecutionContext

    db_path, connection, runner = build_platform_runner(tmp_path)

    async def cancelled_executor(context: JobExecutionContext[dict[str, Any] | None]) -> None:
        assert context.kind == "find"
        raise asyncio.CancelledError()

    try:
        with pytest.raises(asyncio.CancelledError):
            await runner.run_job(
                kind="find",
                origin="cli",
                request={"movie_id": "ABP-420"},
                executor=cancelled_executor,
            )
        job_id = runner.jobs.list_jobs(limit=1)[0]["id"]
    finally:
        connection.close()

    job, events = load_persisted_job_state(db_path, job_id)

    assert job is not None
    assert job["status"] == "failed"
    assert job["finished_at"] is not None
    assert job["error_json"] == {
        "type": "CancelledError",
        "message": "Job execution cancelled",
    }
    assert [event["event_type"] for event in events] == [
        "job.created",
        "job.started",
        "job.cancelled",
    ]
    assert events[-1]["payload_json"] == {
        "type": "CancelledError",
        "message": "Job execution cancelled",
    }


def test_platform_facade_accepts_runner_surface_needed_for_later_job_tasks() -> None:
    from javs.jobs import JobExecutionContext, PlatformJobRunner

    class RunnerWithExecutorSurface(StubPlatformRunner):
        async def run_job(
            self,
            *,
            kind: str,
            origin: str,
            request: object | None,
            executor: object,
        ) -> str:
            return "job-1"

    runner = RunnerWithExecutorSurface()
    facade = PlatformFacade(
        jobs=StubJobsRepository(),
        job_items=StubJobItemsRepository(),
        events=StubJobEventsRepository(),
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    assert facade.runner is runner
    assert inspect.iscoroutinefunction(runner.run_job)
    assert PlatformJobRunner is not None
    assert JobExecutionContext is not None
