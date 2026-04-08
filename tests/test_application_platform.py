"""Tests for shared platform application contracts."""

from __future__ import annotations

import inspect
from pathlib import Path

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
