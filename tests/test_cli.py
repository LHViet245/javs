"""CLI regression tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import javs.config as config_module
import javs.core.engine as engine_module
import javs.scrapers.registry as registry_module
from javs.application import FindMovieResponse, JobStartResponse, JobSummary
from javs.application.find import FindMovieError
from javs.cli import app
from javs.config import JavsConfig
from javs.models.movie import Actress, MovieData, Rating
from javs.services.javlibrary_auth import JavlibraryCredentials

runner = CliRunner()


def _movie_data() -> MovieData:
    return MovieData(
        id="ABP-420",
        title="Test Movie",
        maker="Test Studio",
        release_date=date(2023, 6, 15),
        source="test",
    )


class _UnexpectedEngineUsage:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("CLI find should route through the platform facade.")


def _patch_find_facade(
    monkeypatch,
    *,
    movie: MovieData | None,
    diagnostics: list[dict[str, str]] | None = None,
    capture: dict[str, object] | None = None,
    error: FindMovieError | None = None,
) -> None:
    class DummyFacade:
        def __init__(self) -> None:
            self.last_run_diagnostics = list(diagnostics or [])

        async def find_movie(self, request, *, origin: str = "cli") -> FindMovieResponse:
            if capture is not None:
                capture["request"] = request
                capture["origin"] = origin
            if error is not None:
                raise error
            return FindMovieResponse(
                job=JobSummary(id="job-1", kind="find", status="completed", origin=origin),
                result=movie,
            )

    monkeypatch.setattr(engine_module, "JavsEngine", _UnexpectedEngineUsage)
    monkeypatch.setattr(
        "javs.cli._build_find_facade",
        lambda cfg, config_path: (DummyFacade(), lambda: None),
    )


def _patch_batch_facade(
    monkeypatch,
    *,
    movies: list[MovieData],
    summary: dict[str, int] | None = None,
    diagnostics: list[dict[str, str]] | None = None,
    preview_plan: list[dict[str, str]] | None = None,
    capture: dict[str, object] | None = None,
) -> None:
    class DummyFacade:
        def __init__(self) -> None:
            self.last_run_diagnostics = list(diagnostics or [])
            self.last_run_summary = dict(summary or {})
            self.last_preview_plan = [dict(item) for item in (preview_plan or [])]
            self.last_run_results = list(movies)

        async def start_sort_job(self, request, *, origin: str = "cli") -> JobStartResponse:
            if capture is not None:
                capture["request"] = request
                capture["origin"] = origin
            return JobStartResponse(
                job=JobSummary(id="job-sort-1", kind="sort", status="completed", origin=origin)
            )

        async def start_update_job(self, request, *, origin: str = "cli") -> JobStartResponse:
            if capture is not None:
                capture["request"] = request
                capture["origin"] = origin
            return JobStartResponse(
                job=JobSummary(id="job-update-1", kind="update", status="completed", origin=origin)
            )

    monkeypatch.setattr(engine_module, "JavsEngine", _UnexpectedEngineUsage)
    monkeypatch.setattr(
        "javs.cli._build_platform_facade",
        lambda cfg, config_path: (DummyFacade(), lambda: None),
    )


class TestCliConfigCommand:
    """Test CLI config command contract."""

    def test_config_help_lists_sync_action(self) -> None:
        """The config command help should advertise the sync action."""
        result = runner.invoke(app, ["config", "--help"])

        assert result.exit_code == 0
        assert "csv-paths" in result.stdout
        assert "init-csv" in result.stdout
        assert "javlibrary-cookie" in result.stdout
        assert "javlibrary-test" in result.stdout
        assert "proxy-test" in result.stdout

    def test_config_sync_supports_custom_config_path(self, tmp_path: Path) -> None:
        """config sync should work with an explicit --config path."""
        target = tmp_path / "custom.yaml"

        result = runner.invoke(app, ["config", "sync", "--config", str(target)])

        assert result.exit_code == 0
        assert target.exists()
        assert "Successfully synced and upgraded local config file" in result.stdout

    def test_config_path_prints_custom_path(self, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"

        result = runner.invoke(app, ["config", "path", "--config", str(target)])

        assert result.exit_code == 0
        assert str(target) in result.stdout.replace("\n", "")

    def test_config_edit_creates_missing_file_and_invokes_editor(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "config.yaml"
        created: list[Path] = []
        commands: list[list[str]] = []

        def fake_create_default_config(path: Path) -> None:
            created.append(path)
            path.write_text("created: true\n", encoding="utf-8")

        def fake_run(command: list[str]) -> SimpleNamespace:
            commands.append(command)
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(config_module, "create_default_config", fake_create_default_config)
        monkeypatch.setenv("EDITOR", "fake-editor")
        monkeypatch.setattr("subprocess.run", fake_run)

        result = runner.invoke(app, ["config", "edit", "--config", str(target)])

        assert result.exit_code == 0
        assert created == [target]
        assert commands == [["fake-editor", str(target)]]
        assert target.exists()

    def test_config_unknown_action_reports_error(self) -> None:
        result = runner.invoke(app, ["config", "nope"])

        assert result.exit_code == 0
        assert "Unknown action: nope" in result.stdout

    def test_config_show_masks_sensitive_values(self, monkeypatch) -> None:
        cfg = JavsConfig()
        cfg.sort.metadata.nfo.translate.deepl_api_key = "super-secret"
        cfg.proxy.url = "http://user:pass@example.com:8080"
        cfg.javlibrary.cookie_cf_clearance = "cf-cookie"

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)

        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0
        assert "super-secret" not in result.stdout
        assert "cf-cookie" not in result.stdout
        assert "http://user:pass@example.com:8080" not in result.stdout
        assert '"deepl_api_key": "***"' in result.stdout
        assert '"cookie_cf_clearance": "***"' in result.stdout
        assert '"url": "http://***:***@example.com:8080"' in result.stdout

    def test_config_javlibrary_cookie_prompts_and_saves(self, monkeypatch, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"
        saved: dict[str, str] = {}

        async def fake_configure(cfg, path, **kwargs):
            saved["path"] = str(path)
            cfg.javlibrary.cookie_cf_clearance = "cf-cookie"
            cfg.javlibrary.browser_user_agent = "browser-ua"
            return JavlibraryCredentials("cf-cookie", "browser-ua")

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(
            "javs.services.javlibrary_auth.configure_javlibrary_credentials",
            fake_configure,
        )

        result = runner.invoke(app, ["config", "javlibrary-cookie", "--config", str(target)])

        assert result.exit_code == 0
        assert saved["path"] == str(target)

    def test_config_javlibrary_test_fails_when_credentials_missing(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())

        result = runner.invoke(app, ["config", "javlibrary-test"])

        assert result.exit_code == 1
        assert "Javlibrary credentials are incomplete" in result.stdout

    def test_config_javlibrary_test_runs_validator(self, monkeypatch, tmp_path: Path) -> None:
        cfg = JavsConfig()
        cfg.javlibrary.cookie_cf_clearance = "cf-cookie"
        cfg.javlibrary.browser_user_agent = "browser-ua"
        validated: dict[str, str] = {}

        async def fake_validate(_cfg, credentials):
            validated["cf_clearance"] = credentials.cf_clearance
            validated["user_agent"] = credentials.browser_user_agent

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)
        monkeypatch.setattr(
            "javs.services.javlibrary_auth.validate_javlibrary_credentials",
            fake_validate,
        )

        result = runner.invoke(
            app,
            ["config", "javlibrary-test", "--config", str(tmp_path / "x.yaml")],
        )

        assert result.exit_code == 0
        assert validated == {
            "cf_clearance": "cf-cookie",
            "user_agent": "browser-ua",
        }
        assert "Javlibrary credentials are valid." in result.stdout

    def test_config_csv_paths_shows_effective_paths(self, monkeypatch, tmp_path: Path) -> None:
        cfg = JavsConfig()
        cfg.locations.genre_csv = str(tmp_path / "genres.csv")
        cfg.locations.thumb_csv = str(tmp_path / "thumbs.csv")
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)

        result = runner.invoke(app, ["config", "csv-paths", "--config", str(tmp_path / "x.yaml")])

        assert result.exit_code == 0
        assert "CSV Paths" in result.stdout
        assert str(tmp_path / "genres.csv") in result.stdout
        assert str(tmp_path / "thumbs.csv") in result.stdout

    def test_config_init_csv_initializes_templates(self, monkeypatch, tmp_path: Path) -> None:
        target = tmp_path / "config.yaml"
        recorded: dict[str, object] = {}

        def fake_init(cfg, path):
            recorded["path"] = path
            return SimpleNamespace(
                created=[tmp_path / "genres.csv"],
                existing=[tmp_path / "thumbs.csv"],
                genre_csv_path=tmp_path / "genres.csv",
                thumb_csv_path=tmp_path / "thumbs.csv",
            )

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr("javs.config.csv_templates.init_csv_templates", fake_init)

        result = runner.invoke(app, ["config", "init-csv", "--config", str(target)])

        assert result.exit_code == 0
        assert recorded["path"] == target
        assert "Created CSV template:" in result.stdout
        assert "CSV already exists:" in result.stdout
        assert str(tmp_path / "genres.csv") in result.stdout
        assert str(tmp_path / "thumbs.csv") in result.stdout

    def test_config_proxy_test_runs_diagnostics(self, monkeypatch, tmp_path: Path) -> None:
        from javs.services.proxy_diagnostics import ProxyDiagnosticResult

        called = {}

        async def fake_run_proxy_diagnostics(config):
            called["ran"] = True
            return ProxyDiagnosticResult(ok=True, message="Proxy reachable")

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(
            "javs.services.proxy_diagnostics.run_proxy_diagnostics",
            fake_run_proxy_diagnostics,
        )

        result = runner.invoke(app, ["config", "proxy-test", "--config", str(tmp_path / "x.yaml")])

        assert result.exit_code == 0
        assert "Proxy reachable" in result.stdout
        assert called["ran"] is True

    def test_config_proxy_test_exits_nonzero_on_failure(self, monkeypatch, tmp_path: Path) -> None:
        from javs.services.proxy_diagnostics import ProxyDiagnosticResult

        async def fake_run_proxy_diagnostics(config):
            return ProxyDiagnosticResult(
                ok=False,
                message="Proxy unreachable",
                detail="timed out",
            )

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(
            "javs.services.proxy_diagnostics.run_proxy_diagnostics",
            fake_run_proxy_diagnostics,
        )

        result = runner.invoke(app, ["config", "proxy-test", "--config", str(tmp_path / "x.yaml")])

        assert result.exit_code == 1
        assert "Proxy unreachable" in result.stdout
        assert "timed out" in result.stdout


class TestCliFindCommand:
    """Test `find` command output and exit behavior."""

    def test_cli_find_uses_platform_facade(self, monkeypatch) -> None:
        captured: dict[str, object] = {}

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(
            monkeypatch,
            movie=_movie_data(),
            capture=captured,
        )

        result = runner.invoke(app, ["find", "abp420", "--json", "--scrapers", "dmm,r18dev"])

        assert result.exit_code == 0
        assert captured["origin"] == "cli"
        assert captured["request"].movie_id == "ABP-420"
        assert captured["request"].scraper_names == ["dmm", "r18dev"]
        assert '"id": "ABP-420"' in result.stdout

    def test_find_json_outputs_serialized_movie_data(self, monkeypatch) -> None:
        movie = _movie_data()

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(monkeypatch, movie=movie)

        result = runner.invoke(app, ["find", "ABP-420", "--json", "--scrapers", "dmm,r18dev"])

        assert result.exit_code == 0
        assert '"id": "ABP-420"' in result.stdout
        assert '"title": "Test Movie"' in result.stdout

    def test_status_context_skips_spinner_for_interactive_terminals(self, monkeypatch) -> None:
        from javs.cli import _status_context

        monkeypatch.setattr("javs.services.javlibrary_auth.is_interactive_terminal", lambda: True)

        with _status_context("Searching..."):
            pass

    def test_find_exits_with_code_1_when_no_results(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(monkeypatch, movie=None)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 1
        assert "No results found for ABP-420" in result.stdout

    def test_find_exits_with_code_1_for_structured_find_failure(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(
            monkeypatch,
            movie=None,
            error=FindMovieError(
                job_id="job-1",
                error={"type": "RuntimeError", "message": "boom"},
            ),
        )

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 1
        assert "Find failed for ABP-420: boom" in result.stdout

    def test_find_prints_proxy_failure_summary(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(
            monkeypatch,
            movie=_movie_data(),
            diagnostics=[{"kind": "proxy_unreachable", "scraper": "dmm"}],
        )

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "dmm: proxy unreachable" in result.stdout
        assert "Next: run `javs config proxy-test`." in result.stdout

    def test_find_prints_translation_provider_warning(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(
            monkeypatch,
            movie=_movie_data(),
            diagnostics=[
                {
                    "kind": "translation_provider_unavailable",
                    "scraper": "translate",
                    "detail": "Install googletrans to enable translation.",
                }
            ],
        )

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "translate: translation provider unavailable" in result.stdout
        assert "Install googletrans to enable translation." in result.stdout
        assert "Next: install translation extras with" in result.stdout
        assert '".[translate]"`.' in result.stdout

    def test_find_prints_translation_config_warning(self, monkeypatch) -> None:
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(
            monkeypatch,
            movie=_movie_data(),
            diagnostics=[
                {
                    "kind": "translation_config_invalid",
                    "scraper": "translate",
                    "detail": "DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'.",
                }
            ],
        )

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "translate: translation config invalid" in result.stdout
        assert "DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'." in result.stdout
        assert "Next: update `sort.metadata.nfo.translate` in your config." in result.stdout

    def test_find_renders_compact_layout_with_inline_provenance(self, monkeypatch) -> None:
        long_description = "Translated Plot " + ("detail " * 40)
        long_cover_url = "https://example.com/assets/" + ("cover-segment/" * 8) + "cover.jpg"
        long_trailer_url = (
            "https://example.com/assets/" + ("trailer-segment/" * 8) + "trailer.mp4"
        )
        movie = MovieData(
            id="ABP-420",
            title="Translated Title",
            alternate_title="Original Title",
            description=long_description,
            maker="IdeaPocket",
            label="Premium",
            series="Midnight Series",
            director="Director One",
            release_date=date(2023, 6, 15),
            runtime=120,
            rating=Rating(rating=8.4, votes=1289),
            genres=["Drama", "Romance"],
            actresses=[Actress(first_name="Aoi", last_name="Sora")],
            cover_url=long_cover_url,
            trailer_url=long_trailer_url,
            screenshot_urls=[
                "https://example.com/assets/1.jpg",
                "https://example.com/assets/2.jpg",
            ],
            source="dmm",
            field_sources={
                "title": "deepl",
                "description": "deepl",
                "maker": "dmm",
                "series": "dmm",
                "release_date": "dmm",
                "runtime": "dmm",
                "rating": "r18dev",
                "genres": "r18dev",
                "actresses": "dmm",
                "director": "mgstageja",
                "cover_url": "dmm",
                "trailer_url": "mgstageja",
                "screenshot_urls": "dmm",
            },
        )

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(monkeypatch, movie=movie)

        result = runner.invoke(app, ["find", "ABP-420"])
        normalized_output = " ".join(result.stdout.split())

        assert result.exit_code == 0
        assert "Field Provenance" not in result.stdout
        assert "Identity" not in result.stdout
        assert "ABP-420" in result.stdout
        assert "Translated Title [deepl]" in result.stdout
        assert "Original: Original Title" in normalized_output
        assert "Primary Source" not in result.stdout
        assert "Source" in result.stdout
        assert "Studio" in result.stdout
        assert "Release Date" in result.stdout
        assert "Rating" in result.stdout
        assert "Actresses" in result.stdout
        assert "Cover" in result.stdout
        assert "Trailer" in result.stdout
        assert "Screenshots" in result.stdout
        assert "Series Midnight Series [dmm]" in normalized_output
        assert "2" in result.stdout
        assert long_cover_url not in result.stdout
        assert long_trailer_url not in result.stdout
        assert "https://example.com/assets/cover-segment/cover-segment/" in result.stdout
        assert "..." in result.stdout
        assert "Description" in result.stdout
        assert normalized_output.count("detail") >= 40
        assert "IdeaPocket [dmm]" in normalized_output
        assert "2023-06-15 [dmm]" in normalized_output
        assert "8.4/10 (1289 votes)" in normalized_output
        assert "Drama, Romance [r18dev]" in normalized_output
        assert f"{movie.actresses[0].full_name} [dmm]" in normalized_output
        assert "Director One [mgstageja]" in normalized_output
        assert "[deepl]" in result.stdout
        assert "[dmm]" in result.stdout
        assert "[mgstageja]" in result.stdout

    def test_find_omits_empty_optional_rows_in_compact_view(self, monkeypatch) -> None:
        movie = MovieData(
            id="ABP-420",
            title="Test Movie",
            source="dmm",
            field_sources={"title": "dmm"},
        )

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_find_facade(monkeypatch, movie=movie)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Test Movie [dmm]" in result.stdout
        assert "Label" not in result.stdout
        assert "Series" not in result.stdout
        assert "Director" not in result.stdout
        assert "Cover" not in result.stdout
        assert "Trailer" not in result.stdout
        assert "Screenshots" not in result.stdout
        assert "Field Provenance" not in result.stdout


class TestCliSortAndScrapers:
    """Test sort command wiring and scraper listing output."""

    def test_cli_sort_uses_platform_facade(self, monkeypatch, tmp_path: Path) -> None:
        captured: dict[str, object] = {}

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_batch_facade(
            monkeypatch,
            movies=[_movie_data()],
            summary={"total": 1, "processed": 1, "skipped": 0, "failed": 0, "warnings": 0},
            capture=captured,
        )

        result = runner.invoke(
            app,
            [
                "sort",
                str(tmp_path / "source"),
                str(tmp_path / "dest"),
                "--recurse",
                "--force",
                "--preview",
                "--cleanup-empty-source-dir",
            ],
        )

        assert result.exit_code == 0
        assert captured["origin"] == "cli"
        assert captured["request"].source_path == str(tmp_path / "source")
        assert captured["request"].destination_path == str(tmp_path / "dest")
        assert captured["request"].recurse is True
        assert captured["request"].force is True
        assert captured["request"].preview is True
        assert captured["request"].cleanup_empty_source_dir is True
        assert "Sorted 1 files" in result.stdout

    def test_cli_update_uses_platform_facade(self, monkeypatch, tmp_path: Path) -> None:
        captured: dict[str, object] = {}

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        _patch_batch_facade(
            monkeypatch,
            movies=[_movie_data()],
            summary={"total": 1, "processed": 1, "skipped": 0, "failed": 0, "warnings": 0},
            capture=captured,
        )

        result = runner.invoke(
            app,
            [
                "update",
                str(tmp_path / "library"),
                "--recurse",
                "--force",
                "--preview",
                "--refresh-images",
                "--refresh-trailer",
                "--scrapers",
                "javlibrary,dmm",
            ],
        )

        assert result.exit_code == 0
        assert captured["origin"] == "cli"
        assert captured["request"].source_path == str(tmp_path / "library")
        assert captured["request"].recurse is True
        assert captured["request"].force is True
        assert captured["request"].preview is True
        assert captured["request"].scraper_names == ["javlibrary", "dmm"]
        assert captured["request"].refresh_images is True
        assert captured["request"].refresh_trailer is True
        assert "Updated 1 files" in result.stdout

    def test_sort_passes_flags_to_engine_and_shows_result_table(self, monkeypatch, tmp_path: Path):
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                captured.update(
                    {
                        "source": source,
                        "dest": dest,
                        "recurse": recurse,
                        "force": force,
                        "preview": preview,
                        "cleanup_empty_source_dir": cleanup_empty_source_dir,
                    }
                )
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        result = runner.invoke(
            app,
            ["sort", str(source), str(dest), "--recurse", "--force", "--preview"],
        )

        assert result.exit_code == 0
        assert captured == {
            "source": source,
            "dest": dest,
            "recurse": True,
            "force": True,
            "preview": True,
            "cleanup_empty_source_dir": False,
        }
        assert "Sorted 1 files" in result.stdout
        assert "ABP-420" in result.stdout

    def test_sort_explicitly_enables_cleanup_for_one_run(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                captured["cleanup_empty_source_dir"] = cleanup_empty_source_dir
                return [_movie_data()]

        cfg = JavsConfig()
        cfg.sort.cleanup_empty_source_dir = False
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        result = runner.invoke(
            app,
            [
                "sort",
                str(tmp_path / "source"),
                str(tmp_path / "dest"),
                "--cleanup-empty-source-dir",
            ],
        )

        assert result.exit_code == 0
        assert captured == {"cleanup_empty_source_dir": True}

    def test_sort_explicitly_disables_cleanup_for_one_run(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                captured["cleanup_empty_source_dir"] = cleanup_empty_source_dir
                return [_movie_data()]

        cfg = JavsConfig()
        cfg.sort.cleanup_empty_source_dir = True
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        result = runner.invoke(
            app,
            [
                "sort",
                str(tmp_path / "source"),
                str(tmp_path / "dest"),
                "--no-cleanup-empty-source-dir",
            ],
        )

        assert result.exit_code == 0
        assert captured == {"cleanup_empty_source_dir": False}

    def test_sort_falls_back_to_config_cleanup_setting_when_flag_omitted(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                captured["cleanup_empty_source_dir"] = cleanup_empty_source_dir
                return [_movie_data()]

        cfg = JavsConfig()
        cfg.sort.cleanup_empty_source_dir = True
        monkeypatch.setattr(config_module, "load_config", lambda _path=None: cfg)
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        result = runner.invoke(app, ["sort", str(tmp_path / "source"), str(tmp_path / "dest")])

        assert result.exit_code == 0
        assert captured == {"cleanup_empty_source_dir": True}

    def test_sort_prints_run_summary(self, monkeypatch, tmp_path: Path) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {"kind": "proxy_auth_failed", "scraper": "dmm"},
                    {"kind": "cloudflare_blocked", "scraper": "javlibrary"},
                ]
                self.last_run_summary = {
                    "total": 5,
                    "processed": 1,
                    "skipped": 3,
                    "failed": 1,
                    "warnings": 2,
                }
                self.last_preview_plan = []

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["sort", str(tmp_path / "source"), str(tmp_path / "dest")])

        assert result.exit_code == 0
        assert "Summary: 5 scanned, 1 processed, 3 skipped, 1 failed, 2 warnings" in result.stdout

    def test_sort_preview_prints_preview_plan(self, monkeypatch, tmp_path: Path) -> None:
        source = tmp_path / "source" / "ABP-420.mp4"
        target = tmp_path / "dest" / "ABP-420" / "ABP-420.mp4"

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }
                self.last_preview_plan = [
                    {
                        "source": str(source),
                        "id": "ABP-420",
                        "target": str(target),
                    }
                ]

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(
            app,
            ["sort", str(tmp_path / "source"), str(tmp_path / "dest"), "--preview"],
        )

        assert result.exit_code == 0
        assert "Preview Plan" in result.stdout
        assert "Source" in result.stdout
        assert "Target" in result.stdout
        assert "ABP-420" in result.stdout
        assert "source" in result.stdout
        assert "dest" in result.stdout
        assert "ABP-420.mp4" in result.stdout

    def test_sort_update_passes_flags_to_engine_and_shows_result_table(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }
                self.last_preview_plan = []

            async def update_path(
                self,
                source: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                scraper_names=None,
                refresh_images: bool = False,
                refresh_trailer: bool = False,
            ):
                captured.update(
                    {
                        "source": source,
                        "recurse": recurse,
                        "force": force,
                        "preview": preview,
                        "scraper_names": scraper_names,
                        "refresh_images": refresh_images,
                        "refresh_trailer": refresh_trailer,
                    }
                )
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        library = tmp_path / "library"

        result = runner.invoke(
            app,
            [
                "update",
                str(library),
                "--recurse",
                "--force",
                "--preview",
                "--refresh-images",
                "--refresh-trailer",
                "--scrapers",
                "javlibrary,dmm",
            ],
        )

        assert result.exit_code == 0
        assert captured == {
            "source": library,
            "recurse": True,
            "force": True,
            "preview": True,
            "scraper_names": ["javlibrary", "dmm"],
            "refresh_images": True,
            "refresh_trailer": True,
        }
        assert "Updated 1 files" in result.stdout
        assert "ABP-420" in result.stdout

    def test_update_prints_run_summary(self, monkeypatch, tmp_path: Path) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [{"kind": "proxy_unreachable", "scraper": "dmm"}]
                self.last_run_summary = {
                    "total": 4,
                    "processed": 2,
                    "skipped": 1,
                    "failed": 1,
                    "warnings": 1,
                }

            async def update_path(
                self,
                source: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                scraper_names=None,
                refresh_images: bool = False,
                refresh_trailer: bool = False,
            ):
                return [_movie_data(), _movie_data().model_copy(update={"id": "SSIS-001"})]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["update", str(tmp_path / "library")])

        assert result.exit_code == 0
        assert "Summary: 4 scanned, 2 processed, 1 skipped, 1 failed, 1 warning" in result.stdout

    def test_update_preview_prints_preview_plan(self, monkeypatch, tmp_path: Path) -> None:
        source = tmp_path / "library" / "ABP-420" / "ABP-420.mp4"
        target = tmp_path / "library" / "ABP-420" / "ABP-420.nfo"

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []
                self.last_run_summary = {
                    "total": 1,
                    "processed": 1,
                    "skipped": 0,
                    "failed": 0,
                    "warnings": 0,
                }
                self.last_preview_plan = [
                    {
                        "source": str(source),
                        "id": "ABP-420",
                        "target": str(target),
                    }
                ]

            async def update_path(
                self,
                source: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                scraper_names=None,
                refresh_images: bool = False,
                refresh_trailer: bool = False,
            ):
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["update", str(tmp_path / "library"), "--preview"])

        assert result.exit_code == 0
        assert "Preview Plan" in result.stdout
        assert "Source" in result.stdout
        assert "Target" in result.stdout
        assert "ABP-420" in result.stdout
        assert "library" in result.stdout
        assert ".nfo" in result.stdout

    def test_scrapers_lists_registered_names(self, monkeypatch) -> None:
        monkeypatch.setattr(registry_module.ScraperRegistry, "load_all", lambda: None)
        monkeypatch.setattr(
            registry_module.ScraperRegistry,
            "list_names",
            lambda: ["javlibrary", "dmm"],
        )

        result = runner.invoke(app, ["scrapers"])

        assert result.exit_code == 0
        assert "Available Scrapers" in result.stdout
        assert "dmm" in result.stdout
        assert "javlibrary" in result.stdout

    def test_sort_prints_proxy_failure_summary(self, monkeypatch, tmp_path: Path) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {"kind": "proxy_auth_failed", "scraper": "dmm"},
                    {"kind": "cloudflare_blocked", "scraper": "javlibrary"},
                ]
                self.last_run_summary = {}
                self.last_preview_plan = []

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        result = runner.invoke(app, ["sort", str(source), str(dest)])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "dmm: proxy auth failed" in result.stdout
        assert "javlibrary: Cloudflare blocked" in result.stdout
        assert "Next: run `javs config proxy-test`." in result.stdout
        assert "Next: run `javs config javlibrary-cookie`." in result.stdout

    def test_sort_deduplicates_repeated_diagnostic_hints(self, monkeypatch, tmp_path: Path) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {"kind": "proxy_auth_failed", "scraper": "dmm"},
                    {"kind": "proxy_unreachable", "scraper": "mgstageja"},
                ]
                self.last_run_summary = {}
                self.last_preview_plan = []

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
                cleanup_empty_source_dir: bool = False,
            ):
                return [_movie_data()]

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["sort", str(tmp_path / "source"), str(tmp_path / "dest")])

        assert result.exit_code == 0
        assert "dmm: proxy auth failed" in result.stdout
        assert "mgstageja: proxy unreachable" in result.stdout
        assert result.stdout.count("Next: run `javs config proxy-test`.") == 1
