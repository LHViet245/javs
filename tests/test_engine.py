"""Tests for engine lifecycle and wiring contracts."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from lxml import etree

from javs.config.models import JavsConfig
from javs.core.engine import JavsEngine
from javs.models.file import ScannedFile
from javs.models.movie import MovieData
from javs.services.http import (
    CloudflareBlockedError,
    InvalidProxyAuthError,
    ProxyConnectionFailedError,
)
from javs.services.javlibrary_auth import JavlibraryCredentials
from javs.services.translator import TranslationProviderIssue


class TestJavsEngineHttpClientConfig:
    """Test how JavsEngine wires HttpClient."""

    def test_engine_uses_relaxed_ssl_for_scraping_runtime(self, monkeypatch):
        """Engine should explicitly disable SSL verification for scraper traffic."""
        created: dict[str, object] = {}

        class DummyHttpClient:
            def __init__(self, **kwargs):
                created.update(kwargs)

            async def close(self) -> None:
                return None

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", DummyHttpClient)

        JavsEngine(JavsConfig())

        assert created["verify_ssl"] is False
        assert created["cf_clearance"] == ""
        assert created["cf_user_agent"] == ""

    def test_engine_passes_javlibrary_cf_settings_to_http_client(self, monkeypatch):
        """Engine should wire supported Javlibrary auth fields into HttpClient."""
        created: dict[str, object] = {}
        config = JavsConfig()
        config.javlibrary.cookie_cf_clearance = "cf-cookie"
        config.javlibrary.browser_user_agent = "browser-ua"

        class DummyHttpClient:
            def __init__(self, **kwargs):
                created.update(kwargs)

            async def close(self) -> None:
                return None

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", DummyHttpClient)

        JavsEngine(config)

        assert created["cf_clearance"] == "cf-cookie"
        assert created["cf_user_agent"] == "browser-ua"

    def test_engine_uses_proxy_timeout_when_proxy_enabled(self, monkeypatch):
        """Engine should prefer proxy timeout over download timeout when proxy is enabled."""
        created: dict[str, object] = {}
        config = JavsConfig()
        config.proxy.enabled = True
        config.proxy.url = "http://1.2.3.4:8080"
        config.proxy.timeout_seconds = 11
        config.sort.download.timeout_seconds = 99

        class DummyHttpClient:
            def __init__(self, **kwargs):
                created.update(kwargs)

            async def close(self) -> None:
                return None

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", DummyHttpClient)

        JavsEngine(config)

        assert created["timeout_seconds"] == 11

    def test_engine_uses_injected_runtime_components(self, monkeypatch):
        """Engine should accept an injected runtime bundle without rebuilding components."""
        fake_http = object()
        fake_scanner = object()
        fake_aggregator = object()
        fake_organizer = object()
        runtime = SimpleNamespace(
            http=fake_http,
            scanner=fake_scanner,
            aggregator=fake_aggregator,
            organizer=fake_organizer,
        )

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)

        engine = JavsEngine(JavsConfig(), runtime=runtime)

        assert engine.http is fake_http
        assert engine.scanner is fake_scanner
        assert engine.aggregator is fake_aggregator
        assert engine.organizer is fake_organizer

    def test_engine_exposes_default_runtime_components(self, monkeypatch):
        """Engine should expose the default runtime bundle it constructed."""
        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", _FakeHttpContext)

        engine = JavsEngine(JavsConfig())

        assert engine.runtime.http is engine.http
        assert engine.runtime.scanner is engine.scanner
        assert engine.runtime.aggregator is engine.aggregator
        assert engine.runtime.organizer is engine.organizer


class _FakeHttpContext:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self):
        self.enter_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1

    async def close(self) -> None:
        return None


class TestJavsEngineLifecycle:
    """Regression tests for engine session lifecycle."""

    def _make_engine(self, monkeypatch, config: JavsConfig | None = None) -> JavsEngine:
        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", _FakeHttpContext)
        return JavsEngine(config or JavsConfig())

    def test_find_one_opens_and_closes_http_session_once(self, monkeypatch):
        """find_one() should manage the shared HttpClient context exactly once."""
        engine = self._make_engine(monkeypatch)
        called: dict[str, str] = {}

        async def fake_find(movie_id: str, scraper_names=None, aggregate: bool = True):
            called["movie_id"] = movie_id
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            return MovieData(id=movie_id, title="Found", source="test")

        engine.find = fake_find  # type: ignore[method-assign]

        result = asyncio.run(engine.find_one("ABP-420"))

        assert result is not None
        assert called["movie_id"] == "ABP-420"
        assert engine.http.enter_count == 1
        assert engine.http.exit_count == 1

    def test_find_diagnostics_snapshot_returns_copy(self, monkeypatch):
        """Application callers should be able to snapshot diagnostics safely."""
        engine = self._make_engine(monkeypatch)
        engine.last_run_diagnostics = [{"kind": "proxy_unreachable", "scraper": "dmm"}]

        snapshot = engine.get_last_run_diagnostics()
        snapshot[0]["kind"] = "mutated"

        assert snapshot == [{"kind": "mutated", "scraper": "dmm"}]
        assert engine.last_run_diagnostics == [{"kind": "proxy_unreachable", "scraper": "dmm"}]

    def test_find_preserves_field_sources_through_aggregation_and_translation(
        self, monkeypatch
    ):
        """find() should keep field provenance intact after merge and translation."""
        config = JavsConfig()
        config.sort.metadata.nfo.translate.enabled = True
        engine = self._make_engine(monkeypatch, config=config)
        raw = MovieData(
            id="ABP-420",
            title="Original Title",
            description="Original Plot",
            source="dmm",
            field_sources={"title": "dmm", "description": "dmm"},
        )
        merged = raw.model_copy(deep=True)
        merged.title = "Merged Title"
        merged.field_sources["title"] = "dmm"

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [SimpleNamespace(name="dmm")],
        )

        async def fake_run_scrapers(scrapers, movie_id):
            del scrapers, movie_id
            return [raw]

        monkeypatch.setattr(engine, "_run_scrapers", fake_run_scrapers)
        monkeypatch.setattr(engine.aggregator, "merge", lambda valid: merged)
        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)

        async def fake_translate(data: MovieData, _config) -> MovieData:
            assert data is not raw
            assert data is not merged
            assert data.title == "Merged Title"
            assert data.field_sources == {"title": "dmm", "description": "dmm"}
            data.title = "Translated Title"
            data.field_sources["title"] = "deepl"
            return data

        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        result = asyncio.run(engine.find("ABP-420"))

        assert result is not None
        assert result.title == "Translated Title"
        assert result.description == "Original Plot"
        assert result.field_sources == {"title": "deepl", "description": "dmm"}
        assert merged.title == "Merged Title"
        assert merged.field_sources == {"title": "dmm", "description": "dmm"}
        assert raw.title == "Original Title"
        assert raw.field_sources == {"title": "dmm", "description": "dmm"}

    def test_find_does_not_open_or_close_injected_http_runtime(self, monkeypatch):
        """find() should assume an already-managed HTTP runtime and not own its lifecycle."""
        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        http = _FakeHttpContext()
        runtime = SimpleNamespace(
            http=http,
            scanner=object(),
            aggregator=object(),
            organizer=object(),
        )
        engine = JavsEngine(JavsConfig(), runtime=runtime)

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [SimpleNamespace(name="dmm")],
        )

        async def fake_run_scrapers(scrapers, movie_id):
            del scrapers, movie_id
            return [MovieData(id="ABP-420", title="Found", source="dmm")]

        monkeypatch.setattr(engine, "_run_scrapers", fake_run_scrapers)

        result = asyncio.run(engine.find("ABP-420", aggregate=False))

        assert result is not None
        assert result.id == "ABP-420"
        assert http.enter_count == 0
        assert http.exit_count == 0

    def test_sort_path_keeps_session_open_for_the_whole_batch(self, monkeypatch, tmp_path: Path):
        """sort_path() should open the shared session once for the whole batch."""
        config = JavsConfig(throttle_limit=2, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_files = [
            ScannedFile(
                path=source / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            ScannedFile(
                path=source / "SSIS-001.mp4",
                filename="SSIS-001.mp4",
                basename="SSIS-001",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="SSIS-001",
            ),
        ]
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: scanned_files)

        in_flight = 0
        max_in_flight = 0

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            nonlocal in_flight, max_in_flight
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            await asyncio.sleep(0)
            in_flight -= 1
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del file, data, dest_root, force, preview, nfo_data, cleanup_empty_source_dir
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        result = asyncio.run(engine.sort_path(source, dest, recurse=False))

        assert [movie.id for movie in result] == ["ABP-420", "SSIS-001"]
        assert max_in_flight >= 1
        assert engine.http.enter_count == 1
        assert engine.http.exit_count == 1

    def test_sort_path_passes_cleanup_toggle_to_organizer(
        self, monkeypatch, tmp_path: Path
    ):
        """sort_path() should forward the effective cleanup toggle to organizer.sort_movie()."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_file = ScannedFile(
            path=source / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=source,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del scraper_names, aggregate
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        captured: dict[str, object] = {}

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del file, data, dest_root, force, preview, nfo_data
            captured["cleanup_empty_source_dir"] = cleanup_empty_source_dir
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        result = asyncio.run(
            engine.sort_path(
                source,
                dest,
                cleanup_empty_source_dir=True,
            )
        )

        assert [movie.id for movie in result] == ["ABP-420"]
        assert captured == {"cleanup_empty_source_dir": True}

    def test_sort_path_uses_config_cleanup_toggle_when_kwarg_omitted(
        self, monkeypatch, tmp_path: Path
    ):
        """sort_path() should honor config.sort.cleanup_empty_source_dir when omitted."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.cleanup_empty_source_dir = True
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_file = ScannedFile(
            path=source / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=source,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del scraper_names, aggregate
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        captured: dict[str, object] = {}

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del file, data, dest_root, force, preview, nfo_data
            captured["cleanup_empty_source_dir"] = cleanup_empty_source_dir
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        result = asyncio.run(engine.sort_path(source, dest))

        assert [movie.id for movie in result] == ["ABP-420"]
        assert captured == {"cleanup_empty_source_dir": True}

    def test_find_returns_translated_metadata_for_display(self, monkeypatch):
        """find() should still return translated metadata when translation is enabled."""
        config = JavsConfig()
        config.sort.metadata.nfo.translate.enabled = True
        engine = self._make_engine(monkeypatch, config=config)
        merged = MovieData(id="ABP-420", title="Original", source="fake")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [SimpleNamespace(name="fake")],
        )

        async def fake_run_scrapers(scrapers, movie_id):
            del scrapers, movie_id
            return [merged]

        monkeypatch.setattr(engine, "_run_scrapers", fake_run_scrapers)
        monkeypatch.setattr(engine.aggregator, "merge", lambda valid: merged)

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated"
            return translated

        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        result = asyncio.run(engine.find("ABP-420"))

        assert result is not None
        assert result.title == "Translated"

    def test_update_path_keeps_session_open_for_the_whole_batch(self, monkeypatch, tmp_path: Path):
        """update_path() should share one HTTP session across the whole refresh batch."""
        config = JavsConfig(throttle_limit=2, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        library = tmp_path / "library"
        library.mkdir()

        scanned_files = [
            ScannedFile(
                path=library / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=library,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            ScannedFile(
                path=library / "SSIS-001.mp4",
                filename="SSIS-001.mp4",
                basename="SSIS-001",
                extension=".mp4",
                directory=library,
                size_bytes=1024,
                movie_id="SSIS-001",
            ),
        ]
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: scanned_files)

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            assert scraper_names == ["javlibrary"]
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        async def fake_update_movie(
            file,
            data,
            *,
            force=False,
            preview=False,
            refresh_images=False,
            refresh_trailer=False,
            nfo_data=None,
        ):
            del file, data, nfo_data
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            assert refresh_images is True
            assert refresh_trailer is True
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "update_movie", fake_update_movie)

        result = asyncio.run(
            engine.update_path(
                library,
                scraper_names=["javlibrary"],
                refresh_images=True,
                refresh_trailer=True,
            )
        )

        assert [movie.id for movie in result] == ["ABP-420", "SSIS-001"]
        assert engine.http.enter_count == 1
        assert engine.http.exit_count == 1

    def test_sort_path_preserves_original_naming_data_when_translate_affect_sort_names_disabled(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        """sort_path() should pass original naming data plus translated NFO data separately."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.required_fields = ["title"]
        config.sort.metadata.nfo.translate.enabled = True
        config.sort.metadata.nfo.translate.fields = ["title"]
        config.sort.metadata.nfo.translate.affect_sort_names = False
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_file = ScannedFile(
            path=source / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=source,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])
        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [SimpleNamespace(name="fake")],
        )

        merged = MovieData(id="ABP-420", title="Original", source="fake")

        async def fake_run_scrapers(scrapers, movie_id):
            del scrapers, movie_id
            return [merged]

        monkeypatch.setattr(engine, "_run_scrapers", fake_run_scrapers)
        monkeypatch.setattr(engine.aggregator, "merge", lambda valid: merged)

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated"
            return translated

        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        captured: dict[str, str | None] = {}

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del file, dest_root, force, preview, cleanup_empty_source_dir
            captured["title"] = data.title
            captured["nfo_title"] = nfo_data.title if nfo_data else None
            return None

        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        result = asyncio.run(engine.sort_path(source, dest))

        assert [movie.title for movie in result] == ["Original"]
        assert captured == {"title": "Original", "nfo_title": "Translated"}

    def test_update_path_preserves_original_naming_data_when_translate_affect_sort_names_disabled(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        """update_path() should refresh NFO with translated data without changing naming data."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.required_fields = ["title"]
        config.sort.metadata.nfo.translate.enabled = True
        config.sort.metadata.nfo.translate.fields = ["title"]
        config.sort.metadata.nfo.translate.affect_sort_names = False
        engine = self._make_engine(monkeypatch, config=config)
        library = tmp_path / "library"
        library.mkdir()

        scanned_file = ScannedFile(
            path=library / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=library,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])
        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [SimpleNamespace(name="fake")],
        )

        merged = MovieData(id="ABP-420", title="Original", source="fake")

        async def fake_run_scrapers(scrapers, movie_id):
            del scrapers, movie_id
            return [merged]

        monkeypatch.setattr(engine, "_run_scrapers", fake_run_scrapers)
        monkeypatch.setattr(engine.aggregator, "merge", lambda valid: merged)

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated"
            return translated

        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        captured: dict[str, str | None] = {}

        async def fake_update_movie(
            file,
            data,
            *,
            force=False,
            preview=False,
            refresh_images=False,
            refresh_trailer=False,
            nfo_data=None,
        ):
            del file, force, preview, refresh_images, refresh_trailer
            captured["title"] = data.title
            captured["nfo_title"] = nfo_data.title if nfo_data else None
            return None

        monkeypatch.setattr(engine.organizer, "update_movie", fake_update_movie)

        result = asyncio.run(engine.update_path(library))

        assert [movie.title for movie in result] == ["Original"]
        assert captured == {"title": "Original", "nfo_title": "Translated"}

    def test_sort_path_keeps_original_folder_name_with_translated_nfo(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        """sort_path() should keep original naming while writing translated NFO content."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.nfo.translate.enabled = True
        config.sort.metadata.nfo.translate.fields = ["title", "description"]
        config.sort.metadata.nfo.translate.affect_sort_names = False
        config.sort.download.thumb_img = False
        config.sort.download.poster_img = False
        config.sort.download.actress_img = False
        config.sort.download.screenshot_img = False
        config.sort.download.trailer_vid = False
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        video = source / "ABP-420.mp4"
        video.write_bytes(b"video")

        scanned_file = ScannedFile(
            path=video,
            filename=video.name,
            basename=video.stem,
            extension=video.suffix,
            directory=source,
            size_bytes=video.stat().st_size,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        raw = MovieData(
            id="ABP-420",
            title="Original Title",
            description="Original Description",
            maker="Studio",
            release_date=date(2024, 1, 1),
            cover_url="https://example.com/cover.jpg",
            genres=["Drama"],
            source="fake",
        )

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del movie_id, scraper_names, aggregate
            return raw

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated Title"
            translated.description = "Translated Description"
            return translated

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        result = asyncio.run(engine.sort_path(source, dest))

        folders = list(dest.iterdir())
        assert [movie.title for movie in result] == ["Original Title"]
        assert len(folders) == 1
        assert "Original Title" in folders[0].name
        assert "Translated Title" not in folders[0].name

        nfo_path = folders[0] / "ABP-420.nfo"
        root = etree.fromstring(nfo_path.read_text(encoding="utf-8").encode("utf-8"))
        assert root.find("title").text == "Translated Title"
        assert root.find("plot").text == "Translated Description"

    def test_sort_path_uses_translated_folder_name_when_affect_sort_names_enabled(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        """sort_path() should let translated metadata affect naming when explicitly enabled."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.nfo.translate.enabled = True
        config.sort.metadata.nfo.translate.fields = ["title", "description"]
        config.sort.metadata.nfo.translate.affect_sort_names = True
        config.sort.download.thumb_img = False
        config.sort.download.poster_img = False
        config.sort.download.actress_img = False
        config.sort.download.screenshot_img = False
        config.sort.download.trailer_vid = False
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        video = source / "ABP-420.mp4"
        video.write_bytes(b"video")

        scanned_file = ScannedFile(
            path=video,
            filename=video.name,
            basename=video.stem,
            extension=video.suffix,
            directory=source,
            size_bytes=video.stat().st_size,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        raw = MovieData(
            id="ABP-420",
            title="Original Title",
            description="Original Description",
            maker="Studio",
            release_date=date(2024, 1, 1),
            cover_url="https://example.com/cover.jpg",
            genres=["Drama"],
            source="fake",
        )

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del movie_id, scraper_names, aggregate
            return raw

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated Title"
            translated.description = "Translated Description"
            return translated

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        result = asyncio.run(engine.sort_path(source, dest))

        folders = list(dest.iterdir())
        assert [movie.title for movie in result] == ["Translated Title"]
        assert len(folders) == 1
        assert "Translated Title" in folders[0].name

        nfo_path = folders[0] / "ABP-420.nfo"
        root = etree.fromstring(nfo_path.read_text(encoding="utf-8").encode("utf-8"))
        assert root.find("title").text == "Translated Title"
        assert root.find("plot").text == "Translated Description"

    def test_update_path_rewrites_existing_nfo_with_translated_content(
        self,
        monkeypatch,
        tmp_path: Path,
    ):
        """update_path() should keep existing paths while rewriting NFO with translated text."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.nfo.translate.enabled = True
        config.sort.metadata.nfo.translate.fields = ["title", "description"]
        config.sort.metadata.nfo.translate.affect_sort_names = False
        config.sort.download.thumb_img = False
        config.sort.download.poster_img = False
        config.sort.download.actress_img = False
        config.sort.download.screenshot_img = False
        config.sort.download.trailer_vid = False
        engine = self._make_engine(monkeypatch, config=config)
        folder = tmp_path / "ABP-420 [Studio] - Original Title (2024)"
        folder.mkdir()
        video = folder / "ABP-420.mp4"
        video.write_bytes(b"video")
        nfo_path = folder / "ABP-420.nfo"
        nfo_path.write_text("old", encoding="utf-8")

        scanned_file = ScannedFile(
            path=video,
            filename=video.name,
            basename=video.stem,
            extension=video.suffix,
            directory=folder,
            size_bytes=video.stat().st_size,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        raw = MovieData(
            id="ABP-420",
            title="Original Title",
            description="Original Description",
            maker="Studio",
            release_date=date(2024, 1, 1),
            cover_url="https://example.com/cover.jpg",
            genres=["Drama"],
            source="fake",
        )

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del movie_id, scraper_names, aggregate
            return raw

        async def fake_translate(data: MovieData, _config) -> MovieData:
            translated = data.model_copy(deep=True)
            translated.title = "Translated Title"
            translated.description = "Translated Description"
            return translated

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr("javs.core.engine.get_translation_provider_issue", lambda _config: None)
        monkeypatch.setattr("javs.core.engine.translate_movie_data", fake_translate)

        result = asyncio.run(engine.update_path(folder))

        assert [movie.title for movie in result] == ["Original Title"]
        assert video.exists()
        assert nfo_path.exists()
        root = etree.fromstring(nfo_path.read_text(encoding="utf-8").encode("utf-8"))
        assert root.find("title").text == "Translated Title"
        assert root.find("plot").text == "Translated Description"

    def test_sort_path_skips_movies_missing_required_fields(self, monkeypatch, tmp_path: Path):
        """sort_path() should honor sort.metadata.required_fields before organizing files."""
        config = JavsConfig()
        config.sleep = 0
        config.sort.metadata.required_fields = ["title", "cover_url"]
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_file = ScannedFile(
            path=source / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=source,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            return MovieData(id=movie_id, title="Has title only", source="test")

        async def fail_sort_movie(*args, **kwargs):
            raise AssertionError("sort_movie should not be called when required fields are missing")

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fail_sort_movie)

        result = asyncio.run(engine.sort_path(source, dest))

        assert result == []

    def test_sort_path_does_not_block_next_find_on_organizer_work(
        self, monkeypatch, tmp_path: Path
    ):
        """Scrape pacing should not keep the throttle slot occupied during organizer work."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        config.sort.metadata.required_fields = ["title", "cover_url", "maker", "genres"]
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_files = [
            ScannedFile(
                path=source / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            ScannedFile(
                path=source / "SSIS-001.mp4",
                filename="SSIS-001.mp4",
                basename="SSIS-001",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="SSIS-001",
            ),
        ]
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: scanned_files)

        organizer_started = asyncio.Event()
        release_first_organizer = asyncio.Event()
        second_find_started = asyncio.Event()

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            if movie_id == "SSIS-001":
                second_find_started.set()
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del file, dest_root, force, preview, nfo_data, cleanup_empty_source_dir
            if data.id == "ABP-420":
                organizer_started.set()
                await release_first_organizer.wait()
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        async def exercise() -> list[MovieData]:
            task = asyncio.create_task(engine.sort_path(source, dest))
            await organizer_started.wait()
            await asyncio.wait_for(second_find_started.wait(), timeout=0.2)
            release_first_organizer.set()
            return await task

        result = asyncio.run(exercise())

        assert [item.id for item in result] == ["ABP-420", "SSIS-001"]

    def test_find_one_recovers_javlibrary_after_cloudflare_block(self, monkeypatch):
        """Engine should refresh Javlibrary credentials once, then retry affected scrapers."""
        config = JavsConfig()
        created_http: list[_FakeHttpContext] = []

        class RecoverableHttp(_FakeHttpContext):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.cf_clearance = kwargs.get("cf_clearance", "")
                self.cf_user_agent = kwargs.get("cf_user_agent", "")
                created_http.append(self)

            def update_cf_credentials(self, *, cf_clearance: str, cf_user_agent: str) -> None:
                self.cf_clearance = cf_clearance
                self.cf_user_agent = cf_user_agent

        class JavlibraryScraper:
            name = "javlibrary"

            def __init__(self, http):
                self.http = http
                self.calls = 0

            async def search_and_scrape(self, movie_id: str):
                self.calls += 1
                if self.http.cf_clearance != "fresh-cookie":
                    raise CloudflareBlockedError("blocked")
                return MovieData(id=movie_id, title="Recovered", source="javlibrary")

        async def recover(_error: CloudflareBlockedError):
            return JavlibraryCredentials("fresh-cookie", "fresh-ua")

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", RecoverableHttp)

        engine = JavsEngine(config, cloudflare_recovery_handler=recover)
        scraper = JavlibraryScraper(engine.http)
        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [scraper],
        )

        result = asyncio.run(engine.find_one("ABP-420", aggregate=False))

        assert result is not None
        assert result.title == "Recovered"
        assert scraper.calls == 2
        assert created_http[0].cf_clearance == "fresh-cookie"
        assert created_http[0].cf_user_agent == "fresh-ua"

    def test_find_one_only_attempts_recovery_once_per_run(self, monkeypatch):
        """Cloudflare recovery should not loop when the handler declines to refresh."""
        config = JavsConfig()
        calls = {"recover": 0}

        class RecoverableHttp(_FakeHttpContext):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.cf_clearance = kwargs.get("cf_clearance", "")
                self.cf_user_agent = kwargs.get("cf_user_agent", "")

            def update_cf_credentials(self, *, cf_clearance: str, cf_user_agent: str) -> None:
                self.cf_clearance = cf_clearance
                self.cf_user_agent = cf_user_agent

        class JavlibraryScraper:
            name = "javlibrary"

            async def search_and_scrape(self, movie_id: str):
                raise CloudflareBlockedError(f"blocked:{movie_id}")

        async def recover(_error: CloudflareBlockedError):
            calls["recover"] += 1
            return None

        monkeypatch.setattr("javs.core.engine.setup_logging", lambda **kwargs: None)
        monkeypatch.setattr("javs.core.engine.ScraperRegistry.load_all", lambda: None)
        monkeypatch.setattr("javs.core.engine.HttpClient", RecoverableHttp)

        engine = JavsEngine(config, cloudflare_recovery_handler=recover)
        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [JavlibraryScraper()],
        )

        result = asyncio.run(engine.find_one("ABP-420", aggregate=False))

        assert result is None
        assert calls["recover"] == 1

    def test_find_records_proxy_failure_diagnostics(self, monkeypatch):
        """find_one() should record scraper-specific proxy diagnostics for CLI summaries."""
        engine = self._make_engine(monkeypatch)

        class BrokenScraper:
            name = "dmm"

            async def search_and_scrape(self, movie_id: str):
                raise ProxyConnectionFailedError("proxy unreachable")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [BrokenScraper()],
        )

        result = asyncio.run(engine.find_one("ABP-420", aggregate=False))

        assert result is None
        assert engine.last_run_diagnostics == [
            {"kind": "proxy_unreachable", "scraper": "dmm"}
        ]

    def test_find_resets_previous_run_diagnostics(self, monkeypatch):
        """A new public run should clear stale diagnostics before collecting fresh ones."""
        engine = self._make_engine(monkeypatch)
        engine.last_run_diagnostics = [{"kind": "proxy_auth_failed", "scraper": "old"}]

        class BrokenScraper:
            name = "javlibrary"

            async def search_and_scrape(self, movie_id: str):
                raise CloudflareBlockedError("blocked")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [BrokenScraper()],
        )

        result = asyncio.run(engine.find_one("ABP-420", aggregate=False))

        assert result is None
        assert engine.last_run_diagnostics == [
            {"kind": "cloudflare_blocked", "scraper": "javlibrary"}
        ]

    def test_find_records_proxy_auth_failure_diagnostics(self, monkeypatch):
        """407-style proxy failures should be classified distinctly for CLI output."""
        engine = self._make_engine(monkeypatch)

        class BrokenScraper:
            name = "mgstageja"

            async def search_and_scrape(self, movie_id: str):
                raise InvalidProxyAuthError("bad credentials")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [BrokenScraper()],
        )

        result = asyncio.run(engine.find_one("ABP-420", aggregate=False))

        assert result is None
        assert engine.last_run_diagnostics == [
            {"kind": "proxy_auth_failed", "scraper": "mgstageja"}
        ]

    def test_find_records_translation_provider_unavailable_diagnostic(self, monkeypatch):
        """Missing translation providers should surface as one compact CLI diagnostic."""
        config = JavsConfig()
        config.sort.metadata.nfo.translate.enabled = True
        engine = self._make_engine(monkeypatch, config=config)

        class WorkingScraper:
            name = "r18dev"

            async def search_and_scrape(self, movie_id: str):
                return MovieData(id=movie_id, title="Original", source="r18dev")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [WorkingScraper()],
        )
        monkeypatch.setattr(
            "javs.core.engine.get_translation_provider_issue",
            lambda _config: TranslationProviderIssue(
                kind="translation_provider_unavailable",
                detail="Install googletrans to enable translation.",
            ),
        )

        async def fail_translate(data, config):
            raise AssertionError(
                "translate_movie_data should not be called when provider is missing"
            )

        monkeypatch.setattr("javs.core.engine.translate_movie_data", fail_translate)

        result = asyncio.run(engine.find_one("ABP-420"))

        assert result is not None
        assert result.title == "Original"
        assert engine.last_run_diagnostics == [
            {
                "kind": "translation_provider_unavailable",
                "scraper": "translate",
                "detail": "Install googletrans to enable translation.",
            }
        ]

    def test_find_records_translation_config_invalid_diagnostic(self, monkeypatch):
        """Ambiguous DeepL target languages should surface as a compact CLI diagnostic."""
        config = JavsConfig()
        config.sort.metadata.nfo.translate.enabled = True
        engine = self._make_engine(monkeypatch, config=config)

        class WorkingScraper:
            name = "r18dev"

            async def search_and_scrape(self, movie_id: str):
                return MovieData(id=movie_id, title="Original", source="r18dev")

        monkeypatch.setattr(
            "javs.core.engine.ScraperRegistry.get_enabled",
            lambda *_args, **_kwargs: [WorkingScraper()],
        )
        monkeypatch.setattr(
            "javs.core.engine.get_translation_provider_issue",
            lambda _config: TranslationProviderIssue(
                kind="translation_config_invalid",
                detail="DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'.",
            ),
        )

        async def fail_translate(data, config):
            raise AssertionError(
                "translate_movie_data should not be called when translation config is invalid"
            )

        monkeypatch.setattr("javs.core.engine.translate_movie_data", fail_translate)

        result = asyncio.run(engine.find_one("ABP-420"))

        assert result is not None
        assert result.title == "Original"
        assert engine.last_run_diagnostics == [
            {
                "kind": "translation_config_invalid",
                "scraper": "translate",
                "detail": "DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'.",
            }
        ]

    def test_sort_tracks_processed_skipped_failed_and_warning_counts(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """sort_path() should expose a compact batch summary for CLI output."""
        config = JavsConfig(throttle_limit=2, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_files = [
            ScannedFile(
                path=source / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            ScannedFile(
                path=source / "SSIS-001.mp4",
                filename="SSIS-001.mp4",
                basename="SSIS-001",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="SSIS-001",
            ),
            ScannedFile(
                path=source / "IPX-001.mp4",
                filename="IPX-001.mp4",
                basename="IPX-001",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="IPX-001",
            ),
        ]
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: scanned_files)

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            if movie_id == "SSIS-001":
                return None
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        async def fake_sort_movie(
            file,
            data,
            dest_root,
            force=False,
            preview=False,
            nfo_data=None,
            cleanup_empty_source_dir=False,
        ):
            del data, dest_root, force, preview, nfo_data, cleanup_empty_source_dir
            if file.movie_id == "IPX-001":
                raise RuntimeError("disk full")
            return None

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)
        engine.last_run_diagnostics = [{"kind": "proxy_unreachable", "scraper": "old"}]

        result = asyncio.run(engine.sort_path(source, dest))

        assert [movie.id for movie in result] == ["ABP-420"]
        assert engine.last_run_summary == {
            "total": 3,
            "processed": 1,
            "skipped": 1,
            "failed": 1,
            "warnings": 0,
        }

    def test_sort_preview_collects_preview_plan(self, monkeypatch, tmp_path: Path) -> None:
        """sort_path(preview=True) should expose computed destination paths for CLI preview."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_file = ScannedFile(
            path=source / "ABP-420.mp4",
            filename="ABP-420.mp4",
            basename="ABP-420",
            extension=".mp4",
            directory=source,
            size_bytes=1024,
            movie_id="ABP-420",
        )
        monkeypatch.setattr(engine.scanner, "scan", lambda *_args, **_kwargs: [scanned_file])

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            return MovieData(
                id=movie_id,
                title="Preview Movie",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)

        result = asyncio.run(engine.sort_path(source, dest, preview=True))

        assert [movie.id for movie in result] == ["ABP-420"]
        assert engine.last_preview_plan == [
            {
                "source": str(scanned_file.path),
                "id": "ABP-420",
                "target": str(dest / "ABP-420 [Studio] - Preview Movie (2024)" / "ABP-420.mp4"),
            }
        ]

    def test_sort_preview_resets_previous_preview_plan_between_runs(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Each preview run should replace stale preview rows instead of appending forever."""
        config = JavsConfig(throttle_limit=1, sleep=0)
        engine = self._make_engine(monkeypatch, config=config)
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()

        scanned_files = [
            ScannedFile(
                path=source / "ABP-420.mp4",
                filename="ABP-420.mp4",
                basename="ABP-420",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="ABP-420",
            ),
            ScannedFile(
                path=source / "SSIS-001.mp4",
                filename="SSIS-001.mp4",
                basename="SSIS-001",
                extension=".mp4",
                directory=source,
                size_bytes=1024,
                movie_id="SSIS-001",
            ),
        ]
        calls = {"count": 0}

        def fake_scan(*_args, **_kwargs):
            idx = calls["count"]
            calls["count"] += 1
            return [scanned_files[idx]]

        async def fake_find_merged(movie_id: str, scraper_names=None, aggregate: bool = True):
            del scraper_names, aggregate
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                release_date=date(2024, 1, 1),
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        monkeypatch.setattr(engine.scanner, "scan", fake_scan)
        monkeypatch.setattr(engine, "_find_merged", fake_find_merged)

        first = asyncio.run(engine.sort_path(source, dest, preview=True))
        second = asyncio.run(engine.sort_path(source, dest, preview=True))

        assert [movie.id for movie in first] == ["ABP-420"]
        assert [movie.id for movie in second] == ["SSIS-001"]
        assert engine.last_preview_plan == [
            {
                "source": str(scanned_files[1].path),
                "id": "SSIS-001",
                "target": str(dest / "SSIS-001 [Studio] - SSIS-001 title (2024)" / "SSIS-001.mp4"),
            }
        ]
