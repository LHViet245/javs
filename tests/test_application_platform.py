"""Tests for shared platform application contracts."""

from __future__ import annotations

import inspect

from javs.application import FindMovieRequest, JobSummary, PlatformFacade, SettingsResponse
from javs.config import JavsConfig


def test_find_movie_request_normalizes_movie_id_and_scraper_names() -> None:
    request = FindMovieRequest(
        movie_id=" abp420 ",
        scraper_names=[" JavLibrary ", "DMM", "javlibrary", ""],
    )

    assert request.movie_id == "ABP-420"
    assert request.scraper_names == ["javlibrary", "dmm"]


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


def test_platform_facade_accepts_dependencies_and_exposes_planned_methods() -> None:
    jobs = object()
    job_items = object()
    events = object()
    settings_audit = object()
    history = object()
    runner = object()
    config_loader = object()
    config_saver = object()

    facade = PlatformFacade(
        jobs=jobs,
        job_items=job_items,
        events=events,
        settings_audit=settings_audit,
        history=history,
        runner=runner,
        config_loader=config_loader,
        config_saver=config_saver,
    )

    assert facade.jobs is jobs
    assert facade.job_items is job_items
    assert facade.events is events
    assert facade.settings_audit is settings_audit
    assert facade.history is history
    assert facade.runner is runner
    assert facade.config_loader is config_loader
    assert facade.config_saver is config_saver

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

