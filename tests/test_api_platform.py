"""Tests for the thin platform API adapter."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from javs.api.app import create_app
from javs.application import (
    FindMovieResponse,
    JobStartResponse,
    JobSummary,
    SaveSettingsRequest,
    SaveSettingsResponse,
    SettingsResponse,
    SortJobRequest,
    UpdateJobRequest,
)
from javs.config import JavsConfig
from javs.models.movie import MovieData


class StubFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, str]] = []
        self.settings_path: Path | None = None

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
