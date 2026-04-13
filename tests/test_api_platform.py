"""Tests for the thin platform API adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from javs.api.app import create_app
from javs.application import (
    BatchJobError,
    FindMovieResponse,
    JobDetail,
    JobEventSummary,
    JobItemSummary,
    JobListPage,
    JobListQuery,
    JobStartResponse,
    JobSummary,
    SaveSettingsRequest,
    SaveSettingsResponse,
    SettingsAuditEntry,
    SettingsResponse,
    SettingsSaveError,
    SortJobRequest,
    UpdateJobRequest,
)
from javs.application.find import FindMovieError
from javs.application.settings import SettingsValidationError
from javs.config import JavsConfig
from javs.models.movie import MovieData


class StubFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, str]] = []
        self.settings_path: Path | None = None
        self.job_list_page = JobListPage(
            items=[
                JobSummary(
                    id="job-list-1",
                    kind="sort",
                    status="completed",
                    origin="api",
                    created_at="2026-04-10T09:00:00Z",
                    started_at="2026-04-10T09:00:01Z",
                    finished_at="2026-04-10T09:00:02Z",
                    summary={
                        "total": 3,
                        "processed": 2,
                        "skipped": 1,
                        "failed": 0,
                        "warnings": ["slow path"],
                    },
                    error=None,
                )
            ],
            next_cursor="next-cursor",
        )
        self.jobs_by_id: dict[str, JobDetail] = {
            "job-detail-1": JobDetail(
                job=JobSummary(
                    id="job-detail-1",
                    kind="save_settings",
                    status="completed",
                    origin="api",
                    created_at="2026-04-10T09:00:00Z",
                    started_at="2026-04-10T09:00:01Z",
                    finished_at="2026-04-10T09:00:02Z",
                    summary={
                        "total": 1,
                        "processed": 1,
                        "skipped": 0,
                        "failed": 0,
                        "warnings": [],
                    },
                    error=None,
                ),
                result={
                    "source_path": "/tmp/config.yaml",
                    "config_version": 1,
                },
                items=[
                    JobItemSummary(
                        id=7,
                        item_key="config.yaml",
                        status="completed",
                        source_path="/tmp/config.yaml",
                        dest_path=None,
                        movie_id=None,
                        step="save_settings",
                        message="Saved settings",
                        metadata={"source": "api"},
                        error=None,
                        created_at="2026-04-10T09:00:01Z",
                        started_at="2026-04-10T09:00:01Z",
                        finished_at="2026-04-10T09:00:02Z",
                    )
                ],
                events=[
                    JobEventSummary(
                        id=11,
                        job_id="job-detail-1",
                        event_type="job.started",
                        payload={},
                        created_at="2026-04-10T09:00:01Z",
                    )
                ],
                settings_audit=SettingsAuditEntry(
                    id=3,
                    job_id="job-detail-1",
                    source_path="~/.javs/config.yaml",
                    config_version=1,
                    before={},
                    after={},
                    change_summary={},
                    created_at="2026-04-10T09:00:02Z",
                ),
            ),
            "job-empty-1": JobDetail(
                job=JobSummary(
                    id="job-empty-1",
                    kind="save_settings",
                    status="completed",
                    origin="api",
                    created_at="2026-04-10T09:05:00Z",
                    summary={
                        "total": 1,
                        "processed": 1,
                        "skipped": 0,
                        "failed": 0,
                        "warnings": [],
                    },
                ),
                result={"saved": 1},
                items=[],
                events=[],
                settings_audit=None,
            ),
        }

    async def find_movie(self, request, *, origin: str = "cli") -> FindMovieResponse:
        self.calls.append(("find_movie", request, origin))
        return FindMovieResponse(
            job=JobSummary(
                id="job-find-1",
                kind="find",
                status="completed",
                origin=origin,
            ),
            result=MovieData(id="ABP-420", title="Facade Movie", maker="Studio", source="stub"),
        )

    async def start_sort_job(self, request, *, origin: str = "cli") -> JobStartResponse:
        self.calls.append(("start_sort_job", request, origin))
        return JobStartResponse(
            job=JobSummary(
                id="job-sort-1",
                kind="sort",
                status="completed",
                origin=origin,
            )
        )

    async def start_update_job(self, request, *, origin: str = "cli") -> JobStartResponse:
        self.calls.append(("start_update_job", request, origin))
        return JobStartResponse(
            job=JobSummary(
                id="job-update-1",
                kind="update",
                status="completed",
                origin=origin,
            )
        )

    def list_jobs(self, query: JobListQuery | None = None) -> JobListPage:
        self.calls.append(("list_jobs", query, "api"))
        if query is not None and query.limit > 100:
            raise ValueError("limit must be between 1 and 100")
        return self.job_list_page

    def get_job(self, job_id: str) -> JobDetail | None:
        self.calls.append(("get_job", job_id, "api"))
        return self.jobs_by_id.get(job_id)

    def get_settings(self, source_path: Path) -> SettingsResponse:
        self.calls.append(("get_settings", source_path, "api"))
        self.settings_path = source_path
        config = JavsConfig()
        return SettingsResponse(
            config=config,
            source_path=str(source_path),
            config_version=config.config_version,
        )

    async def save_settings(
        self,
        request: SaveSettingsRequest,
        *,
        origin: str = "cli",
    ) -> SaveSettingsResponse:
        self.calls.append(("save_settings", request, origin))
        config = JavsConfig()
        return SaveSettingsResponse(
            job=JobSummary(
                id="job-save-1",
                kind="save_settings",
                status="completed",
                origin=origin,
            ),
            settings=SettingsResponse(
                config=config,
                source_path=request.source_path or "~/.javs/config.yaml",
                config_version=config.config_version,
            ),
        )


@pytest.fixture
def api_app() -> tuple[object, StubFacade]:
    facade = StubFacade()
    return create_app(facade), facade


@pytest.mark.asyncio
async def test_post_find_job_routes_through_facade(api_app: tuple[object, StubFacade]) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/jobs/find",
            json={"movie_id": " abp420 ", "scraper_names": [" JavLibrary ", "DMM"]},
        )

    assert response.status_code == 200
    assert response.json() == FindMovieResponse(
        job=JobSummary(
            id="job-find-1",
            kind="find",
            status="completed",
            origin="api",
        ),
        result=MovieData(id="ABP-420", title="Facade Movie", maker="Studio", source="stub"),
    ).model_dump(mode="json")
    assert len(facade.calls) == 1
    call_name, request, origin = facade.calls[0]
    assert call_name == "find_movie"
    assert origin == "api"
    assert request.movie_id == "ABP-420"
    assert request.scraper_names == ["javlibrary", "dmm"]


@pytest.mark.asyncio
async def test_post_sort_and_update_jobs_route_through_facade(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sort_response = await client.post(
            "/jobs/sort",
            json={
                "source_path": "/library/incoming",
                "destination_path": "/library/sorted",
                "recurse": True,
                "force": True,
                "preview": False,
                "cleanup_empty_source_dir": True,
            },
        )
        update_response = await client.post(
            "/jobs/update",
            json={
                "source_path": "/library/sorted",
                "recurse": True,
                "force": False,
                "preview": True,
                "scraper_names": [" JavLibrary ", "DMM", "javlibrary"],
                "refresh_images": True,
                "refresh_trailer": True,
            },
        )

    assert sort_response.status_code == 200
    assert sort_response.json() == JobStartResponse(
        job=JobSummary(
            id="job-sort-1",
            kind="sort",
            status="completed",
            origin="api",
        )
    ).model_dump(mode="json")
    assert update_response.status_code == 200
    assert update_response.json() == JobStartResponse(
        job=JobSummary(
            id="job-update-1",
            kind="update",
            status="completed",
            origin="api",
        )
    ).model_dump(mode="json")
    assert [call[0] for call in facade.calls] == ["start_sort_job", "start_update_job"]
    sort_request = facade.calls[0][1]
    update_request = facade.calls[1][1]
    assert isinstance(sort_request, SortJobRequest)
    assert isinstance(update_request, UpdateJobRequest)
    assert facade.calls[0][2] == "api"
    assert facade.calls[1][2] == "api"
    assert sort_request.source_path == "/library/incoming"
    assert sort_request.destination_path == "/library/sorted"
    assert sort_request.cleanup_empty_source_dir is True
    assert update_request.source_path == "/library/sorted"
    assert update_request.scraper_names == ["javlibrary", "dmm"]
    assert update_request.refresh_images is True
    assert update_request.refresh_trailer is True


@pytest.mark.asyncio
async def test_get_and_post_settings_route_through_facade(
    api_app: tuple[object, StubFacade],
    monkeypatch,
    tmp_path: Path,
) -> None:
    from javs.api.routes import settings as settings_routes

    app, facade = api_app
    default_path = tmp_path / "config.yaml"
    monkeypatch.setattr(settings_routes, "get_default_config_path", lambda: default_path)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        get_response = await client.get("/settings")
        post_response = await client.post(
            "/settings",
            json={
                "source_path": str(tmp_path / "custom.yaml"),
                "changes": {"proxy": {"enabled": True, "url": "http://127.0.0.1:8888"}},
            },
        )

    assert get_response.status_code == 200
    expected_settings = SettingsResponse(
        config=JavsConfig(),
        source_path=str(default_path),
        config_version=1,
    )
    assert get_response.json() == expected_settings.model_dump(mode="json")
    assert post_response.status_code == 200
    expected_post = SaveSettingsResponse(
        job=JobSummary(
            id="job-save-1",
            kind="save_settings",
            status="completed",
            origin="api",
        ),
        settings=SettingsResponse(
            config=JavsConfig(),
            source_path=str(tmp_path / "custom.yaml"),
            config_version=1,
        ),
    )
    assert post_response.json() == expected_post.model_dump(mode="json")
    assert facade.settings_path == default_path
    assert [call[0] for call in facade.calls] == ["get_settings", "save_settings"]
    assert facade.calls[1][2] == "api"
    save_request = facade.calls[1][1]
    assert isinstance(save_request, SaveSettingsRequest)
    assert save_request.source_path == str(tmp_path / "custom.yaml")
    assert save_request.changes == {
        "proxy": {"enabled": True, "url": "http://127.0.0.1:8888"}
    }


@pytest.mark.asyncio
async def test_get_jobs_routes_through_facade_and_serializes_typed_page(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/jobs",
            params={
                "limit": 1,
                "kind": "sort",
                "status": "completed",
                "origin": "api",
                "q": "job-detail-1",
            },
        )

    assert response.status_code == 200
    assert response.json() == facade.job_list_page.model_dump(mode="json")
    assert len(facade.calls) == 1
    call_name, query, origin = facade.calls[0]
    assert call_name == "list_jobs"
    assert origin == "api"
    assert isinstance(query, JobListQuery)
    assert query.limit == 1
    assert query.kind == "sort"
    assert query.status == "completed"
    assert query.origin == "api"
    assert query.q == "job-detail-1"


@pytest.mark.asyncio
async def test_get_jobs_rejects_page_sizes_over_the_maximum(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs", params={"limit": 101})

    assert response.status_code == 400
    assert response.json() == {"detail": "limit must be between 1 and 100"}
    assert len(facade.calls) == 1
    call_name, query, origin = facade.calls[0]
    assert call_name == "list_jobs"
    assert origin == "api"
    assert isinstance(query, JobListQuery)
    assert query.limit == 101


@pytest.mark.asyncio
async def test_get_jobs_forwards_job_id_and_dest_path_search_queries(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.get("/jobs", params={"q": "job-detail-1"})
        second_response = await client.get(
            "/jobs",
            params={"q": "/library/sorted/ABP-420.nfo"},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert [call[0] for call in facade.calls] == ["list_jobs", "list_jobs"]
    assert isinstance(facade.calls[0][1], JobListQuery)
    assert isinstance(facade.calls[1][1], JobListQuery)
    assert facade.calls[0][1].q == "job-detail-1"
    assert facade.calls[1][1].q == "/library/sorted/ABP-420.nfo"


@pytest.mark.asyncio
async def test_get_job_detail_routes_through_facade_and_serializes_typed_detail(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs/job-detail-1")

    assert response.status_code == 200
    assert response.json() == facade.jobs_by_id["job-detail-1"].model_dump(mode="json")
    assert len(facade.calls) == 1
    call_name, job_id, origin = facade.calls[0]
    assert call_name == "get_job"
    assert origin == "api"
    assert job_id == "job-detail-1"


@pytest.mark.asyncio
async def test_get_job_detail_returns_empty_arrays_when_job_has_no_history(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs/job-empty-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload == facade.jobs_by_id["job-empty-1"].model_dump(mode="json")
    assert payload["items"] == []
    assert payload["events"] == []
    assert payload["settings_audit"] is None


@pytest.mark.asyncio
async def test_get_job_detail_returns_404_for_unknown_job_id(
    api_app: tuple[object, StubFacade],
) -> None:
    app, facade = api_app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/jobs/job-missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not found."}
    assert len(facade.calls) == 1
    call_name, job_id, origin = facade.calls[0]
    assert call_name == "get_job"
    assert origin == "api"
    assert job_id == "job-missing"


@pytest.mark.asyncio
async def test_get_settings_returns_500_when_loading_fails() -> None:
    class FailingFacade(StubFacade):
        def get_settings(self, source_path: Path) -> SettingsResponse:
            self.calls.append(("get_settings", source_path, "api"))
            raise ValueError("config load failed")

    app = create_app(FailingFacade())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/settings")

    assert response.status_code == 500
    assert response.json() == {"detail": "config load failed"}


@pytest.mark.asyncio
async def test_get_settings_returns_500_when_validation_fails() -> None:
    class FailingFacade(StubFacade):
        def get_settings(self, source_path: Path) -> SettingsResponse:
            self.calls.append(("get_settings", source_path, "api"))
            raise RuntimeError("config validation failed")

    app = create_app(FailingFacade())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/settings")

    assert response.status_code == 500
    assert response.json() == {"detail": "config validation failed"}


@pytest.mark.asyncio
async def test_application_errors_are_translated_to_structured_http_responses() -> None:
    class FailingFacade(StubFacade):
        async def find_movie(self, request, *, origin: str = "cli") -> FindMovieResponse:
            self.calls.append(("find_movie", request, origin))
            raise FindMovieError(
                job_id="job-find-failed",
                error={"type": "RuntimeError", "message": "find exploded"},
            )

        async def start_sort_job(self, request, *, origin: str = "cli") -> JobStartResponse:
            self.calls.append(("start_sort_job", request, origin))
            raise BatchJobError(
                job_id="job-sort-failed",
                kind="sort",
                error={"type": "RuntimeError", "message": "sort exploded"},
            )

        async def save_settings(
            self,
            request: SaveSettingsRequest,
            *,
            origin: str = "cli",
        ) -> SaveSettingsResponse:
            self.calls.append(("save_settings", request, origin))
            raise SettingsSaveError(
                job_id="job-save-failed",
                error={"type": "SettingsValidationError", "message": "save exploded"},
            )

    app = create_app(FailingFacade())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        find_response = await client.post("/jobs/find", json={"movie_id": "ABP-420"})
        sort_response = await client.post(
            "/jobs/sort",
            json={
                "source_path": "/library/incoming",
                "destination_path": "/library/sorted",
            },
        )
        save_response = await client.post(
            "/settings",
            json={"changes": {"proxy": {"enabled": True, "url": "http://127.0.0.1:8888"}}},
        )

    assert find_response.status_code == 409
    assert find_response.json() == {
        "detail": "RuntimeError for job job-find-failed: find exploded",
        "job_id": "job-find-failed",
        "error": {"type": "RuntimeError", "message": "find exploded"},
    }
    assert sort_response.status_code == 409
    assert sort_response.json() == {
        "detail": "RuntimeError for sort job job-sort-failed: sort exploded",
        "job_id": "job-sort-failed",
        "error": {"type": "RuntimeError", "message": "sort exploded"},
    }
    assert save_response.status_code == 409
    assert save_response.json() == {
        "detail": "SettingsValidationError for settings job job-save-failed: save exploded",
        "job_id": "job-save-failed",
        "error": {"type": "SettingsValidationError", "message": "save exploded"},
    }


@pytest.mark.asyncio
async def test_settings_validation_errors_are_translated_to_structured_http_responses() -> None:
    class ValidationFailingFacade(StubFacade):
        async def save_settings(
            self,
            request: SaveSettingsRequest,
            *,
            origin: str = "cli",
        ) -> SaveSettingsResponse:
            self.calls.append(("save_settings", request, origin))
            raise SettingsValidationError(
                "Changing database.path through shared settings save is not supported yet."
            )

    app = create_app(ValidationFailingFacade())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/settings",
            json={"changes": {"database": {"path": "/tmp/other-platform.db"}}},
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Changing database.path through shared settings save is not supported yet.",
        "job_id": None,
        "error": {
            "type": "SettingsValidationError",
            "message": "Changing database.path through shared settings save is not supported yet.",
        },
    }
