"""Tests for engine lifecycle and wiring contracts."""

from __future__ import annotations

import asyncio
from pathlib import Path

from javs.config.models import JavsConfig
from javs.core.engine import JavsEngine
from javs.models.file import ScannedFile
from javs.models.movie import MovieData
from javs.services.http import CloudflareBlockedError
from javs.services.javlibrary_auth import JavlibraryCredentials


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

        async def fake_find(movie_id: str, scraper_names=None, aggregate: bool = True):
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
                release_date=None,
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                source="test",
            )

        async def fake_sort_movie(file, data, dest_root, force=False, preview=False):
            assert engine.http.enter_count == 1
            assert engine.http.exit_count == 0
            return None

        engine.find = fake_find  # type: ignore[method-assign]
        monkeypatch.setattr(engine.organizer, "sort_movie", fake_sort_movie)

        result = asyncio.run(engine.sort_path(source, dest, recurse=False))

        assert len(result) == 0
        assert max_in_flight >= 1
        assert engine.http.enter_count == 1
        assert engine.http.exit_count == 1

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

        async def fake_find(movie_id: str, scraper_names=None, aggregate: bool = True):
            return MovieData(id=movie_id, title="Has title only", source="test")

        async def fail_sort_movie(*args, **kwargs):
            raise AssertionError("sort_movie should not be called when required fields are missing")

        engine.find = fake_find  # type: ignore[method-assign]
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

        async def fake_find(movie_id: str, scraper_names=None, aggregate: bool = True):
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

        async def fake_sort_movie(file, data, dest_root, force=False, preview=False):
            if data.id == "ABP-420":
                organizer_started.set()
                await release_first_organizer.wait()
            return None

        engine.find = fake_find  # type: ignore[method-assign]
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
