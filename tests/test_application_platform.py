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
    JobEventSummary,
    JobItemSummary,
    JobListPage,
    JobListQuery,
    JobStartResponse,
    JobSummary,
    PlatformFacade,
    RealtimeEvent,
    SaveSettingsRequest,
    SaveSettingsResponse,
    SettingsAuditEntry,
    SettingsAuditRepository,
    SettingsResponse,
    SettingsSaveError,
    SettingsView,
    SortJobRequest,
    UpdateJobRequest,
    build_job_detail,
    build_job_item_summary,
    build_job_summary,
    get_job_detail,
    get_settings_view,
    list_jobs,
    normalize_job_summary_payload,
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


def test_job_list_query_defaults_limit_and_normalizes_filters() -> None:
    query = JobListQuery(
        cursor="  next-cursor  ",
        kind="  Sort  ",
        status="  COMPLETED  ",
        origin="  API  ",
        q="  search term  ",
    )

    assert query.limit == 20
    assert query.cursor == "next-cursor"
    assert query.kind == "sort"
    assert query.status == "completed"
    assert query.origin == "api"
    assert query.q == "search term"


def test_job_list_page_uses_typed_summary_items() -> None:
    page = JobListPage(items=[], next_cursor=None)

    assert page.items == []
    assert page.next_cursor is None


def test_history_contracts_are_reexported_from_application_package() -> None:
    from javs.application import JobListPage, JobListQuery, RealtimeEvent

    assert JobListQuery is not None
    assert JobListPage is not None
    assert RealtimeEvent is not None


def test_realtime_event_serializes_typed_event_payload() -> None:
    event = RealtimeEvent(
        type="job.event",
        job_id="job-1",
        event=JobEventSummary(
            id=7,
            job_id="job-1",
            event_type="job.completed",
            payload={"result": "ok"},
            created_at="2026-04-08T00:00:00Z",
        ),
    )

    assert event.model_dump() == {
        "type": "job.event",
        "job_id": "job-1",
        "event": {
            "id": 7,
            "job_id": "job-1",
            "event_type": "job.completed",
            "job_item_id": None,
            "payload": {"result": "ok"},
            "created_at": "2026-04-08T00:00:00Z",
        },
    }


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


def test_job_summary_payload_normalizes_missing_summary_shape() -> None:
    assert normalize_job_summary_payload(None) == {
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "warnings": [],
    }


def test_job_detail_allows_optional_settings_audit() -> None:
    detail = JobDetail(
        job=JobSummary(id="job-1", kind="sort", status="completed", origin="cli")
    )

    assert detail.settings_audit is None
    assert detail.events == []


def test_build_job_detail_normalizes_missing_summary_shape() -> None:
    detail = build_job_detail(
        {
            "id": "job-1",
            "kind": "sort",
            "status": "completed",
            "origin": "cli",
        }
    )

    assert detail.job.summary == {
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "warnings": [],
    }


def test_list_jobs_returns_typed_page_with_normalized_summary_payload() -> None:
    class StubHistoryRepository:
        def list_jobs(self, *, limit: int | None = None) -> list[dict[str, object]]:
            jobs = [
                {
                    "id": "job-1",
                    "kind": "sort",
                    "status": "completed",
                    "origin": "cli",
                    "created_at": "2026-04-08T00:00:00Z",
                    "summary_json": {"processed": 2, "warnings": "slow path"},
                },
                {
                    "id": "job-2",
                    "kind": "sort",
                    "status": "failed",
                    "origin": "api",
                    "created_at": "2026-04-08T00:01:00Z",
                    "summary_json": {"failed": 1},
                },
            ]
            return jobs if limit is None else jobs[:limit]

    page = list_jobs(StubHistoryRepository(), JobListQuery(limit=1))

    assert page == JobListPage(
        items=[
            JobSummary(
                id="job-1",
                kind="sort",
                status="completed",
                origin="cli",
                created_at="2026-04-08T00:00:00Z",
                summary={
                    "total": 0,
                    "processed": 2,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": ["slow path"],
                },
            )
        ],
        next_cursor=None,
    )


def test_list_jobs_rejects_advanced_query_fields_until_repository_support_exists() -> None:
    class RejectingHistoryRepository:
        def list_jobs(self, *, limit: int | None = None) -> list[dict[str, object]]:
            raise AssertionError("list_jobs should not be called for unsupported queries")

    for field, value in [
        ("cursor", "missing"),
        ("kind", "sort"),
        ("status", "completed"),
        ("origin", "cli"),
        ("q", "search"),
    ]:
        with pytest.raises(NotImplementedError):
            list_jobs(RejectingHistoryRepository(), JobListQuery(**{field: value}))


def test_get_job_detail_returns_events_and_settings_audit() -> None:
    class StubHistoryRepository:
        def get(self, job_id: str) -> dict[str, object] | None:
            if job_id != "job-1":
                return None
            return {
                "id": "job-1",
                "kind": "sort",
                "status": "completed",
                "origin": "cli",
                "summary_json": {"processed": 1},
                "result_json": {"destination": "/sorted"},
            }

    class StubJobItemsRepository:
        def list_for_job(self, job_id: str) -> list[dict[str, object]]:
            return [
                {
                    "id": 7,
                    "job_id": job_id,
                    "item_key": "item-1",
                    "status": "completed",
                }
            ]

    class StubJobEventsRepository:
        def list_for_job(self, job_id: str) -> list[dict[str, object]]:
            return [
                {
                    "id": 9,
                    "job_id": job_id,
                    "event_type": "job.completed",
                    "payload_json": {"summary": {"processed": 1}},
                    "created_at": "2026-04-08T00:02:00Z",
                }
            ]

    class StubSettingsAuditRepository:
        def get_for_job(self, job_id: str) -> dict[str, object] | None:
            if job_id != "job-1":
                return None
            return {
                "id": 11,
                "job_id": "job-1",
                "source_path": "/tmp/config.yaml",
                "config_version": 1,
                "before_json": {"proxy": {"enabled": False}},
                "after_json": {"proxy": {"enabled": True}},
                "change_summary_json": {"changed": ["proxy.enabled"]},
                "created_at": "2026-04-08T00:03:00Z",
            }

        def list_entries(self) -> list[dict[str, object]]:
            return []

    detail = get_job_detail(
        StubHistoryRepository(),
        "job-1",
        job_items=StubJobItemsRepository(),
        events=StubJobEventsRepository(),
        settings_audit=StubSettingsAuditRepository(),
    )

    assert detail == JobDetail(
        job=JobSummary(
            id="job-1",
            kind="sort",
            status="completed",
            origin="cli",
            summary={
                "total": 0,
                "processed": 1,
                "skipped": 0,
                "failed": 0,
                "warnings": [],
            },
        ),
        result={"destination": "/sorted"},
        items=[
            JobItemSummary(
                id=7,
                item_key="item-1",
                status="completed",
            )
        ],
        events=[
            JobEventSummary(
                id=9,
                job_id="job-1",
                event_type="job.completed",
                payload={"summary": {"processed": 1}},
                created_at="2026-04-08T00:02:00Z",
            )
        ],
        settings_audit=SettingsAuditEntry(
            id=11,
            job_id="job-1",
            source_path="/tmp/config.yaml",
            config_version=1,
            before={"proxy": {"enabled": False}},
            after={"proxy": {"enabled": True}},
            change_summary={"changed": ["proxy.enabled"]},
            created_at="2026-04-08T00:03:00Z",
        ),
    )


def test_get_settings_view_returns_typed_audit_rows() -> None:
    config = JavsConfig()
    view = get_settings_view(
        config=config,
        source_path="/tmp/config.yaml",
        config_version=1,
    )

    assert view == SettingsView(
        config=config,
        source_path="/tmp/config.yaml",
        config_version=1,
    )


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
        job=JobSummary(
            id="job-1",
            kind="sort",
            status="completed",
            origin="cli",
            created_at="2026-04-08T00:00:00Z",
            started_at="2026-04-08T00:01:00Z",
            finished_at="2026-04-08T00:02:00Z",
            summary={
                "total": 0,
                "processed": 2,
                "skipped": 0,
                "failed": 0,
                "warnings": [],
            },
            error=None,
        ),
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
    def create_entry(self, **kwargs: object) -> int:
        return 1

    def get_for_job(self, job_id: str) -> dict[str, object] | None:
        return None

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


def test_cli_platform_facade_threads_shared_event_hub(tmp_path: Path) -> None:
    from javs.application import FindMovieRequest
    from javs.cli import _build_platform_facade
    from javs.jobs import JobExecutionContext, JobExecutionResult

    cfg = JavsConfig()
    cfg.database.path = str(tmp_path / "cli-platform.db")

    facade, cleanup = _build_platform_facade(cfg, tmp_path / "config.yaml")

    async def run_job() -> tuple[str, list[object]]:
        subscriber = facade.runner.hub.subscribe()

        async def successful_executor(
            context: JobExecutionContext[FindMovieRequest],
        ) -> JobExecutionResult:
            assert context.job_id
            return JobExecutionResult(result={"movie_id": context.request.movie_id})

        job_id = await facade.runner.run_job(
            kind="find",
            origin="cli",
            request=FindMovieRequest(movie_id="ABP-420"),
            executor=successful_executor,
        )
        queued_events = [
            await asyncio.wait_for(subscriber.get(), timeout=1),
            await asyncio.wait_for(subscriber.get(), timeout=1),
            await asyncio.wait_for(subscriber.get(), timeout=1),
        ]
        return job_id, queued_events

    try:
        job_id, queued_events = asyncio.run(run_job())
    finally:
        cleanup()

    assert job_id
    assert [event.event_type for event in queued_events] == [
        "job.created",
        "job.started",
        "job.completed",
    ]


@pytest.mark.asyncio
async def test_platform_job_events_emit_publishes_to_shared_hub(platform_runtime) -> None:
    from javs.jobs.events import PlatformJobEvents, RealtimeEvent

    job_id = platform_runtime.jobs.create_job(
        kind="find",
        origin="cli",
        request_json={"movie_id": "ABP-420"},
    )
    subscriber = platform_runtime.hub.subscribe()

    job_events = PlatformJobEvents(
        repository=platform_runtime.events,
        job_id=job_id,
        hub=platform_runtime.hub,
    )

    event_id = job_events.emit(
        "job.started",
        payload={"kind": "find", "origin": "cli"},
    )

    queued_event = await asyncio.wait_for(subscriber.get(), timeout=1)

    assert isinstance(queued_event, RealtimeEvent)
    assert queued_event.id == event_id
    assert queued_event.job_id == job_id
    assert queued_event.event_type == "job.started"
    assert queued_event.job_item_id is None
    assert queued_event.payload == {"kind": "find", "origin": "cli"}
    assert platform_runtime.events.list_for_job(job_id)[0]["event_type"] == "job.started"


@pytest.mark.asyncio
async def test_platform_runner_publishes_live_events_to_shared_hub(platform_runtime) -> None:
    from javs.application import FindMovieRequest
    from javs.jobs import JobExecutionContext, JobExecutionResult
    from javs.jobs.events import RealtimeEvent

    subscriber = platform_runtime.hub.subscribe()

    async def successful_executor(
        context: JobExecutionContext[FindMovieRequest],
    ) -> JobExecutionResult:
        assert context.job_id
        assert context.events is not None
        return JobExecutionResult(
            result={"movie_id": context.request.movie_id},
            summary={"matched": 1},
        )

    job_id = await platform_runtime.runner.run_job(
        kind="find",
        origin="cli",
        request=FindMovieRequest(movie_id="ABP-420"),
        executor=successful_executor,
    )

    queued_events = [
        await asyncio.wait_for(subscriber.get(), timeout=1),
        await asyncio.wait_for(subscriber.get(), timeout=1),
        await asyncio.wait_for(subscriber.get(), timeout=1),
    ]

    assert job_id
    assert [event.event_type for event in queued_events] == [
        "job.created",
        "job.started",
        "job.completed",
    ]
    assert all(isinstance(event, RealtimeEvent) for event in queued_events)
    assert queued_events[-1].payload == {
        "result": {"movie_id": "ABP-420"},
        "summary": {"matched": 1},
    }


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


def load_persisted_job_items(db_path: Path, job_id: str) -> list[dict[str, Any]]:
    from javs.database.connection import open_database
    from javs.database.repositories.job_items import JobItemsRepository

    with open_database(db_path) as connection:
        items = JobItemsRepository(connection)
        return items.list_for_job(job_id)


def load_persisted_settings_audit(db_path: Path) -> list[dict[str, Any]]:
    from javs.database.connection import open_database
    from javs.database.repositories.settings_audit import SettingsAuditRepository

    with open_database(db_path) as connection:
        audit = SettingsAuditRepository(connection)
        return audit.list_entries()


def test_facade_get_settings_returns_shared_settings_response(tmp_path: Path) -> None:
    from javs.config import load_config, save_config

    config_path = tmp_path / "config.yaml"
    config = JavsConfig()
    config.proxy.enabled = True
    config.proxy.url = "http://127.0.0.1:8888"
    save_config(config, config_path)

    facade = PlatformFacade(
        jobs=StubJobsRepository(),
        job_items=StubJobItemsRepository(),
        events=StubJobEventsRepository(),
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=StubPlatformRunner(),
        config_loader=load_config,
        config_saver=save_test_config,
    )

    response = facade.get_settings(config_path)

    assert response == SettingsResponse(
        config=load_config(config_path),
        source_path=str(config_path),
        config_version=1,
    )


def build_history_facade(tmp_path: Path) -> tuple[PlatformFacade, Any, Any, Any, Any]:
    from javs.config import load_config, save_config
    from javs.database.connection import open_database
    from javs.database.migrations import initialize_database
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.database.repositories.settings_audit import SettingsAuditRepository

    db_path = tmp_path / "history.db"
    initialize_database(db_path)
    connection = open_database(db_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    settings_audit = SettingsAuditRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=settings_audit,
        history=StubPlatformHistory(),
        runner=StubPlatformRunner(),
        config_loader=load_config,
        config_saver=save_config,
    )
    return facade, connection, jobs, events, settings_audit


def test_facade_list_jobs_returns_typed_paginated_results(tmp_path: Path) -> None:
    facade, connection, jobs, _, _ = build_history_facade(tmp_path)

    try:
        first_job_id = jobs.create_job(kind="find", origin="cli")
        second_job_id = jobs.create_job(kind="sort", origin="api")
        jobs.update_job(first_job_id, summary_json={"processed": 1})
        jobs.update_job(second_job_id, summary_json={"processed": 2})

        page = facade.list_jobs(JobListQuery(limit=1))
        next_page = facade.list_jobs(JobListQuery(limit=1, cursor=page.next_cursor))
    finally:
        connection.close()

    assert isinstance(page, JobListPage)
    assert page.next_cursor is not None
    assert len(page.items) == 1
    assert len(next_page.items) == 1
    assert {page.items[0].id, next_page.items[0].id} == {
        first_job_id,
        second_job_id,
    }
    assert page.items[0].summary["processed"] in {1, 2}
    assert next_page.items[0].summary["processed"] in {1, 2}
    assert page.items[0].summary != next_page.items[0].summary


def test_facade_list_jobs_forwards_filters_and_cursor_queries(tmp_path: Path) -> None:
    facade, connection, jobs, _, _ = build_history_facade(tmp_path)

    try:
        jobs.create_job(kind="find", origin="cli")
        sort_job_id = jobs.create_job(kind="sort", origin="api")
        jobs.update_job(sort_job_id, summary_json={"processed": 2})

        page = facade.list_jobs(JobListQuery(limit=10, kind="sort"))
    finally:
        connection.close()

    assert page.next_cursor is None
    assert page.items == [
        JobSummary(
            id=sort_job_id,
            kind="sort",
            status="pending",
            origin="api",
            created_at=page.items[0].created_at,
            summary={
                "total": 0,
                "processed": 2,
                "skipped": 0,
                "failed": 0,
                "warnings": [],
            },
        )
    ]


def test_settings_audit_facade_protocol_exposes_get_for_job() -> None:
    assert hasattr(SettingsAuditRepository, "get_for_job")


def test_facade_get_job_returns_detail_with_events_and_settings_audit(
    tmp_path: Path,
) -> None:
    facade, connection, jobs, events, settings_audit = build_history_facade(tmp_path)

    try:
        job_id = jobs.create_job(kind="save_settings", origin="cli")
        jobs.update_job(
            job_id,
            result_json={
                "config_version": 1,
                "source_path": "/tmp/config.yaml",
            },
        )
        events.add_event(
            job_id=job_id,
            event_type="job.completed",
            payload_json={"summary": {"saved": 1}},
        )
        settings_audit.create_entry(
            job_id=job_id,
            source_path="/tmp/config.yaml",
            config_version=1,
            before_json={"proxy": {"enabled": False}},
            after_json={"proxy": {"enabled": True}},
            change_summary_json={"changed": ["proxy.enabled"]},
        )

        detail = facade.get_job(job_id)
    finally:
        connection.close()

    assert detail is not None
    assert detail.job == JobSummary(
        id=job_id,
        kind="save_settings",
        status="pending",
        origin="cli",
        created_at=detail.job.created_at,
        summary={
            "total": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "warnings": [],
        },
    )
    assert detail.result == {
        "config_version": 1,
        "source_path": "/tmp/config.yaml",
    }
    assert detail.items == []
    assert detail.events == [
        JobEventSummary(
            id=detail.events[0].id,
            job_id=job_id,
            event_type="job.completed",
            payload={"summary": {"saved": 1}},
            created_at=detail.events[0].created_at,
        )
    ]
    assert detail.settings_audit == SettingsAuditEntry(
        id=detail.settings_audit.id,
        job_id=job_id,
        source_path="/tmp/config.yaml",
        config_version=1,
        before={"proxy": {"enabled": False}},
        after={"proxy": {"enabled": True}},
        change_summary={"changed": ["proxy.enabled"]},
        created_at=detail.settings_audit.created_at,
    )


@pytest.mark.asyncio
async def test_save_settings_writes_yaml_and_settings_audit_rows(tmp_path: Path) -> None:
    from javs.config import load_config, save_config
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.database.repositories.settings_audit import SettingsAuditRepository

    config_path = tmp_path / "config.yaml"
    initial = JavsConfig()
    save_config(initial, config_path)

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    settings_audit = SettingsAuditRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=settings_audit,
        history=StubPlatformHistory(),
        runner=runner,
        config_loader=load_config,
        config_saver=save_config,
    )

    try:
        response = await facade.save_settings(
            SaveSettingsRequest(
                source_path=str(config_path),
                changes={
                    "proxy": {
                        "enabled": True,
                        "url": "http://127.0.0.1:8888",
                    }
                },
            ),
            origin="cli",
        )
    finally:
        connection.close()

    persisted_config = load_config(config_path)
    job, persisted_events = load_persisted_job_state(db_path, response.job.id)
    audit_rows = load_persisted_settings_audit(db_path)

    assert response == SaveSettingsResponse(
        job=JobSummary(
            id=response.job.id,
            kind="save_settings",
            status="completed",
            origin="cli",
            created_at=response.job.created_at,
            started_at=response.job.started_at,
            finished_at=response.job.finished_at,
            summary={"saved": 1},
            error=None,
        ),
        settings=SettingsResponse(
            config=persisted_config,
            source_path=str(config_path),
            config_version=1,
        ),
    )
    assert persisted_config.proxy.enabled is True
    assert persisted_config.proxy.url == "http://127.0.0.1:8888"
    assert job is not None
    assert job["request_json"] == {
        "changes": {"proxy": {"enabled": True, "url": "http://127.0.0.1:8888"}},
        "source_path": str(config_path),
    }
    assert job["result_json"] == {
        "config_version": 1,
        "source_path": str(config_path),
    }
    assert job["summary_json"] == {"saved": 1}
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.completed",
    ]
    assert audit_rows == [
        {
            "id": audit_rows[0]["id"],
            "job_id": response.job.id,
            "source_path": str(config_path),
            "config_version": 1,
            "before_json": initial.model_dump(mode="json"),
            "after_json": persisted_config.model_dump(mode="json"),
            "change_summary_json": {"changed": ["proxy.enabled", "proxy.url"]},
            "created_at": audit_rows[0]["created_at"],
        }
    ]


@pytest.mark.asyncio
async def test_save_settings_restores_yaml_when_audit_write_fails(tmp_path: Path) -> None:
    from javs.config import load_config, save_config
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository

    class FailingSettingsAuditRepository:
        def create_entry(self, **kwargs: object) -> int:
            raise RuntimeError("audit insert exploded")

        def list_entries(self) -> list[dict[str, object]]:
            return []

    config_path = tmp_path / "config.yaml"
    initial = JavsConfig()
    save_config(initial, config_path)

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=FailingSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        config_loader=load_config,
        config_saver=save_config,
    )

    try:
        with pytest.raises(SettingsSaveError) as exc_info:
            await facade.save_settings(
                SaveSettingsRequest(
                    source_path=str(config_path),
                    changes={
                        "proxy": {
                            "enabled": True,
                            "url": "http://127.0.0.1:8888",
                        }
                    },
                ),
                origin="cli",
            )
    finally:
        connection.close()

    restored_config = load_config(config_path)
    job, persisted_events = load_persisted_job_state(db_path, exc_info.value.job_id)

    assert restored_config == initial
    assert exc_info.value.error == {
        "type": "RuntimeError",
        "message": "audit insert exploded",
    }
    assert job is not None
    assert job["status"] == "failed"
    assert job["error_json"] == {
        "type": "RuntimeError",
        "message": "audit insert exploded",
    }
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.failed",
    ]


@pytest.mark.asyncio
async def test_save_settings_restores_yaml_when_terminal_job_fails_after_write(
    tmp_path: Path,
) -> None:
    from javs.config import load_config, save_config
    from javs.config.loader import apply_settings_changes
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository, utc_now
    from javs.database.repositories.settings_audit import SettingsAuditRepository
    from javs.jobs.events import PlatformJobEvents
    from javs.jobs.executor import JobExecutionContext, serialize_job_value

    class FailedTerminalRunner:
        def __init__(
            self,
            *,
            jobs: JobsRepository,
            events: JobEventsRepository,
        ) -> None:
            self.jobs = jobs
            self.events = events
            self.connection = jobs.connection

        async def run_job(
            self,
            *,
            kind: str,
            origin: str,
            request: object | None,
            executor,
        ) -> str:
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

            await executor(
                JobExecutionContext(
                    job_id=job_id,
                    kind=kind,
                    origin=origin,
                    request=request,
                    events=job_events,
                )
            )

            failure = {
                "type": "TerminalPersistenceError",
                "message": "job completion persistence failed",
            }
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
            return job_id

    config_path = tmp_path / "config.yaml"
    initial = JavsConfig()
    save_config(initial, config_path)

    db_path, connection, _runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    settings_audit = SettingsAuditRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=settings_audit,
        history=StubPlatformHistory(),
        runner=FailedTerminalRunner(jobs=jobs, events=events),
        config_loader=load_config,
        config_saver=save_config,
    )

    try:
        with pytest.raises(SettingsSaveError) as exc_info:
            await facade.save_settings(
                SaveSettingsRequest(
                    source_path=str(config_path),
                    changes={
                        "proxy": {
                            "enabled": True,
                            "url": "http://127.0.0.1:8888",
                        }
                    },
                ),
                origin="cli",
            )
    finally:
        connection.close()

    restored_config = load_config(config_path)
    job, persisted_events = load_persisted_job_state(db_path, exc_info.value.job_id)
    audit_rows = load_persisted_settings_audit(db_path)

    assert restored_config == initial
    assert exc_info.value.error == {
        "type": "TerminalPersistenceError",
        "message": "job completion persistence failed",
    }
    assert job is not None
    assert job["status"] == "failed"
    assert job["error_json"] == exc_info.value.error
    assert audit_rows == [
        {
            "id": audit_rows[0]["id"],
            "job_id": exc_info.value.job_id,
            "source_path": str(config_path),
            "config_version": 1,
            "before_json": initial.model_dump(mode="json"),
            "after_json": apply_settings_changes(
                initial,
                {"proxy": {"enabled": True, "url": "http://127.0.0.1:8888"}},
            ).model_dump(mode="json"),
            "change_summary_json": {"changed": ["proxy.enabled", "proxy.url"]},
            "created_at": audit_rows[0]["created_at"],
        }
    ]
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.failed",
    ]


@pytest.mark.asyncio
async def test_save_settings_rejects_database_path_changes(tmp_path: Path) -> None:
    from javs.config import load_config, save_config
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.database.repositories.settings_audit import SettingsAuditRepository

    config_path = tmp_path / "config.yaml"
    initial = JavsConfig()
    save_config(initial, config_path)

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    settings_audit = SettingsAuditRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=settings_audit,
        history=StubPlatformHistory(),
        runner=runner,
        config_loader=load_config,
        config_saver=save_config,
    )

    try:
        with pytest.raises(SettingsSaveError) as exc_info:
            await facade.save_settings(
                SaveSettingsRequest(
                    source_path=str(config_path),
                    changes={"database": {"path": str(tmp_path / "other-platform.db")}},
                ),
                origin="cli",
            )
    finally:
        connection.close()

    restored_config = load_config(config_path)
    job, persisted_events = load_persisted_job_state(db_path, exc_info.value.job_id)
    audit_rows = load_persisted_settings_audit(db_path)

    assert restored_config.database.path == initial.database.path
    assert exc_info.value.error == {
        "type": "SettingsValidationError",
        "message": "Changing database.path through shared settings save is not supported yet.",
    }
    assert job is not None
    assert job["status"] == "failed"
    assert job["error_json"] == exc_info.value.error
    assert audit_rows == []
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.failed",
    ]


@pytest.mark.asyncio
async def test_facade_find_movie_returns_job_and_result(tmp_path: Path) -> None:
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.models.movie import MovieData

    class StubFindEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[str, list[str] | None]] = []
            self._diagnostics = [{"kind": "proxy_unreachable", "scraper": "dmm"}]

        async def find_one(
            self,
            movie_id: str,
            scraper_names: list[str] | None = None,
            aggregate: bool = True,
        ) -> MovieData | None:
            assert aggregate is True
            self.calls.append((movie_id, scraper_names))
            return MovieData(id=movie_id, title="Facade Movie", source="stub")

        def get_last_run_diagnostics(self) -> list[dict[str, str]]:
            return [dict(item) for item in self._diagnostics]

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    engine = StubFindEngine()
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        find_engine_factory=lambda: engine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        response = await facade.find_movie(
            FindMovieRequest(movie_id=" abp420 ", scraper_names=[" DMM ", ""]),
            origin="cli",
        )
    finally:
        connection.close()

    job, persisted_events = load_persisted_job_state(db_path, response.job.id)

    assert response.job.kind == "find"
    assert response.job.status == "completed"
    assert response.result is not None
    assert response.result.id == "ABP-420"
    assert facade.last_run_diagnostics == [{"kind": "proxy_unreachable", "scraper": "dmm"}]
    assert engine.calls == [("ABP-420", ["dmm"])]
    assert job is not None
    assert job["request_json"] == {"movie_id": "ABP-420", "scraper_names": ["dmm"]}
    assert job["result_json"]["id"] == "ABP-420"
    assert job["summary_json"] == {"matched": 1}
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.completed",
    ]


@pytest.mark.asyncio
async def test_facade_start_sort_job_persists_summary_and_item_history(tmp_path: Path) -> None:
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.job_items import JobItemsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.models.movie import MovieData

    source = tmp_path / "incoming"
    dest = tmp_path / "sorted"
    source.mkdir()
    dest.mkdir()

    class StubSortEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, Path, bool, bool, bool, bool | None]] = []
            self.last_run_diagnostics = [{"kind": "proxy_unreachable", "scraper": "dmm"}]
            self.last_run_summary = {
                "total": 2,
                "processed": 1,
                "skipped": 1,
                "failed": 0,
                "warnings": 1,
            }
            self.last_preview_plan = [
                {
                    "source": str(source / "ABP-420.mp4"),
                    "id": "ABP-420",
                    "target": str(dest / "ABP-420" / "ABP-420.mp4"),
                }
            ]
            self.last_run_items = [
                {
                    "item_key": "ABP-420",
                    "status": "completed",
                    "source_path": str(source / "ABP-420.mp4"),
                    "dest_path": str(dest / "ABP-420" / "ABP-420.mp4"),
                    "movie_id": "ABP-420",
                    "step": "sort",
                    "message": "Sorted successfully",
                    "metadata": {"preview": False},
                },
                {
                    "item_key": "SSIS-001",
                    "status": "skipped",
                    "source_path": str(source / "SSIS-001.mp4"),
                    "movie_id": "SSIS-001",
                    "step": "sort",
                    "message": "No data found",
                    "metadata": {"preview": False},
                },
            ]

        async def sort_path(
            self,
            source_path: Path,
            destination_path: Path,
            recurse: bool = False,
            force: bool = False,
            preview: bool = False,
            cleanup_empty_source_dir: bool | None = None,
        ) -> list[MovieData]:
            self.calls.append(
                (
                    source_path,
                    destination_path,
                    recurse,
                    force,
                    preview,
                    cleanup_empty_source_dir,
                )
            )
            return [MovieData(id="ABP-420", title="Facade Movie", source="stub")]

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    job_items = JobItemsRepository(connection)
    events = JobEventsRepository(connection)
    engine = StubSortEngine()
    facade = PlatformFacade(
        jobs=jobs,
        job_items=job_items,
        events=events,
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        sort_engine_factory=lambda: engine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        response = await facade.start_sort_job(
            SortJobRequest(
                source_path=str(source),
                destination_path=str(dest),
                recurse=True,
                force=True,
                preview=False,
                cleanup_empty_source_dir=True,
            ),
            origin="cli",
        )
    finally:
        connection.close()

    job, persisted_events = load_persisted_job_state(db_path, response.job.id)
    persisted_items = load_persisted_job_items(db_path, response.job.id)

    assert response == JobStartResponse(
        job=JobSummary(
            id=response.job.id,
            kind="sort",
            status="completed",
            origin="cli",
            created_at=response.job.created_at,
            started_at=response.job.started_at,
            finished_at=response.job.finished_at,
            summary={"total": 2, "processed": 1, "skipped": 1, "failed": 0, "warnings": 1},
            error=None,
        )
    )
    assert facade.last_run_diagnostics == [{"kind": "proxy_unreachable", "scraper": "dmm"}]
    assert facade.last_run_summary == {
        "total": 2,
        "processed": 1,
        "skipped": 1,
        "failed": 0,
        "warnings": 1,
    }
    assert facade.last_preview_plan == [
        {
            "source": str(source / "ABP-420.mp4"),
            "id": "ABP-420",
            "target": str(dest / "ABP-420" / "ABP-420.mp4"),
        }
    ]
    assert [movie.id for movie in facade.last_run_results] == ["ABP-420"]
    assert facade.last_run_items == [
        {
            "item_key": "ABP-420",
            "status": "completed",
            "source_path": str(source / "ABP-420.mp4"),
            "dest_path": str(dest / "ABP-420" / "ABP-420.mp4"),
            "movie_id": "ABP-420",
            "step": "sort",
            "message": "Sorted successfully",
            "metadata": {"preview": False},
        },
        {
            "item_key": "SSIS-001",
            "status": "skipped",
            "source_path": str(source / "SSIS-001.mp4"),
            "movie_id": "SSIS-001",
            "step": "sort",
            "message": "No data found",
            "metadata": {"preview": False},
        },
    ]
    assert engine.calls == [(source, dest, True, True, False, True)]
    assert job is not None
    assert job["request_json"] == {
        "source_path": str(source),
        "destination_path": str(dest),
        "recurse": True,
        "force": True,
        "preview": False,
        "cleanup_empty_source_dir": True,
    }
    assert len(job["result_json"]) == 1
    assert job["result_json"][0]["id"] == "ABP-420"
    assert job["result_json"][0]["title"] == "Facade Movie"
    assert job["result_json"][0]["source"] == "stub"
    assert job["summary_json"] == {
        "total": 2,
        "processed": 1,
        "skipped": 1,
        "failed": 0,
        "warnings": 1,
    }
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.item.recorded",
        "job.item.recorded",
        "job.completed",
    ]
    assert persisted_items == [
        {
            "id": persisted_items[0]["id"],
            "job_id": response.job.id,
            "item_key": "ABP-420",
            "source_path": str(source / "ABP-420.mp4"),
            "dest_path": str(dest / "ABP-420" / "ABP-420.mp4"),
            "movie_id": "ABP-420",
            "status": "completed",
            "step": "sort",
            "message": "Sorted successfully",
            "metadata_json": {"preview": False},
            "error_json": None,
            "created_at": persisted_items[0]["created_at"],
            "started_at": None,
            "finished_at": None,
        },
        {
            "id": persisted_items[1]["id"],
            "job_id": response.job.id,
            "item_key": "SSIS-001",
            "source_path": str(source / "SSIS-001.mp4"),
            "dest_path": None,
            "movie_id": "SSIS-001",
            "status": "skipped",
            "step": "sort",
            "message": "No data found",
            "metadata_json": {"preview": False},
            "error_json": None,
            "created_at": persisted_items[1]["created_at"],
            "started_at": None,
            "finished_at": None,
        },
    ]


@pytest.mark.asyncio
async def test_facade_start_update_job_persists_summary_and_item_history(tmp_path: Path) -> None:
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.job_items import JobItemsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.models.movie import MovieData

    library = tmp_path / "library"
    library.mkdir()

    class StubUpdateEngine:
        def __init__(self) -> None:
            self.calls: list[tuple[Path, bool, bool, bool, list[str] | None, bool, bool]] = []
            self.last_run_diagnostics = []
            self.last_run_summary = {
                "total": 1,
                "processed": 1,
                "skipped": 0,
                "failed": 0,
                "warnings": 0,
            }
            self.last_preview_plan = []
            self.last_run_items = [
                {
                    "item_key": "ABP-420",
                    "status": "completed",
                    "source_path": str(library / "ABP-420" / "ABP-420.mp4"),
                    "dest_path": str(library / "ABP-420" / "ABP-420.nfo"),
                    "movie_id": "ABP-420",
                    "step": "update",
                    "message": "Updated successfully",
                    "metadata": {"refresh_images": True, "refresh_trailer": True},
                }
            ]

        async def update_path(
            self,
            source_path: Path,
            recurse: bool = False,
            force: bool = False,
            preview: bool = False,
            scraper_names: list[str] | None = None,
            refresh_images: bool = False,
            refresh_trailer: bool = False,
        ) -> list[MovieData]:
            self.calls.append(
                (
                    source_path,
                    recurse,
                    force,
                    preview,
                    scraper_names,
                    refresh_images,
                    refresh_trailer,
                )
            )
            return [MovieData(id="ABP-420", title="Updated Movie", source="stub")]

    db_path, connection, runner = build_platform_runner(tmp_path)
    jobs = JobsRepository(connection)
    job_items = JobItemsRepository(connection)
    events = JobEventsRepository(connection)
    engine = StubUpdateEngine()
    facade = PlatformFacade(
        jobs=jobs,
        job_items=job_items,
        events=events,
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        update_engine_factory=lambda: engine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        response = await facade.start_update_job(
            UpdateJobRequest(
                source_path=str(library),
                recurse=True,
                force=True,
                preview=False,
                scraper_names=[" javlibrary ", "dmm", "javlibrary"],
                refresh_images=True,
                refresh_trailer=True,
            ),
            origin="cli",
        )
    finally:
        connection.close()

    job, persisted_events = load_persisted_job_state(db_path, response.job.id)
    persisted_items = load_persisted_job_items(db_path, response.job.id)

    assert response.job.kind == "update"
    assert response.job.status == "completed"
    assert facade.last_run_summary == {
        "total": 1,
        "processed": 1,
        "skipped": 0,
        "failed": 0,
        "warnings": 0,
    }
    assert [movie.id for movie in facade.last_run_results] == ["ABP-420"]
    assert engine.calls == [
        (library, True, True, False, ["javlibrary", "dmm"], True, True)
    ]
    assert job is not None
    assert job["request_json"] == {
        "source_path": str(library),
        "recurse": True,
        "force": True,
        "preview": False,
        "scraper_names": ["javlibrary", "dmm"],
        "refresh_images": True,
        "refresh_trailer": True,
    }
    assert len(job["result_json"]) == 1
    assert job["result_json"][0]["id"] == "ABP-420"
    assert job["result_json"][0]["title"] == "Updated Movie"
    assert job["result_json"][0]["source"] == "stub"
    assert job["summary_json"] == {
        "total": 1,
        "processed": 1,
        "skipped": 0,
        "failed": 0,
        "warnings": 0,
    }
    assert [event["event_type"] for event in persisted_events] == [
        "job.created",
        "job.started",
        "job.item.recorded",
        "job.completed",
    ]
    assert persisted_items[0]["item_key"] == "ABP-420"
    assert persisted_items[0]["status"] == "completed"
    assert persisted_items[0]["dest_path"] == str(library / "ABP-420" / "ABP-420.nfo")
    assert persisted_items[0]["metadata_json"] == {
        "refresh_images": True,
        "refresh_trailer": True,
    }


@pytest.mark.asyncio
async def test_facade_start_sort_job_raises_for_failed_terminal_job(tmp_path: Path) -> None:
    from javs.application import BatchJobError
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository

    db_path, connection, runner = build_platform_runner(tmp_path)
    del db_path
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)

    class StubSortEngine:
        last_preview_plan: list[dict[str, str]] = []
        last_run_diagnostics: list[dict[str, str]] = []
        last_run_items: list[dict[str, object]] = []
        last_run_summary: dict[str, int] = {}

        async def sort_path(
            self,
            source: Path,
            dest: Path,
            recurse: bool = False,
            force: bool = False,
            preview: bool = False,
            cleanup_empty_source_dir: bool | None = None,
        ) -> list[object]:
            del source, dest, recurse, force, preview, cleanup_empty_source_dir
            raise RuntimeError("sort exploded")

    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        sort_engine_factory=StubSortEngine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        with pytest.raises(BatchJobError) as exc_info:
            await facade.start_sort_job(
                SortJobRequest(
                    source_path=str(tmp_path / "source"),
                    destination_path=str(tmp_path / "dest"),
                ),
                origin="cli",
            )
    finally:
        connection.close()

    assert exc_info.value.kind == "sort"
    assert exc_info.value.error == {"type": "RuntimeError", "message": "sort exploded"}


@pytest.mark.asyncio
async def test_facade_find_movie_requires_synchronous_terminal_job_state(tmp_path: Path) -> None:
    from javs.application.find import FindMovieError
    from javs.database.repositories.jobs import JobsRepository

    class StubRunner:
        async def run_find(self, request, *, origin: str, executor=None) -> str:
            del request, origin, executor
            return "job-async"

    class StubFindEngine:
        async def find_one(self, movie_id: str, scraper_names=None, aggregate: bool = True):
            del movie_id, scraper_names, aggregate
            return None

        def get_last_run_diagnostics(self) -> list[dict[str, str]]:
            return []

    db_path, connection, runner = build_platform_runner(tmp_path)
    del db_path, runner
    jobs = JobsRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=StubJobEventsRepository(),
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=StubRunner(),
        find_engine_factory=StubFindEngine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        with pytest.raises(FindMovieError) as exc_info:
            await facade.find_movie(FindMovieRequest(movie_id="ABP-420"), origin="cli")
    finally:
        connection.close()

    assert exc_info.value.job_id == "job-async"
    assert exc_info.value.error == {
        "type": "FindContractError",
        "message": "Find requires a terminal job row to be persisted before the runner returns.",
        "status": "missing",
    }


@pytest.mark.asyncio
async def test_facade_find_movie_raises_structured_error_for_failed_job(tmp_path: Path) -> None:
    from javs.application.find import FindMovieError
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository

    db_path, connection, runner = build_platform_runner(tmp_path)
    del db_path
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)

    class StubFindEngine:
        async def find_one(self, movie_id: str, scraper_names=None, aggregate: bool = True):
            del movie_id, scraper_names, aggregate
            raise RuntimeError("boom")

        def get_last_run_diagnostics(self) -> list[dict[str, str]]:
            return [{"kind": "proxy_unreachable", "scraper": "dmm"}]

    facade = PlatformFacade(
        jobs=jobs,
        job_items=StubJobItemsRepository(),
        events=events,
        settings_audit=StubSettingsAuditRepository(),
        history=StubPlatformHistory(),
        runner=runner,
        find_engine_factory=StubFindEngine,
        config_loader=load_test_config,
        config_saver=save_test_config,
    )

    try:
        with pytest.raises(FindMovieError) as exc_info:
            await facade.find_movie(FindMovieRequest(movie_id="ABP-420"), origin="cli")
    finally:
        connection.close()

    assert exc_info.value.job_id
    assert exc_info.value.error == {"type": "RuntimeError", "message": "boom"}
    assert "RuntimeError" in str(exc_info.value)
    assert facade.last_run_diagnostics == [{"kind": "proxy_unreachable", "scraper": "dmm"}]


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
