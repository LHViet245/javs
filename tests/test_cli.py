"""CLI regression tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import javs.config as config_module
import javs.core.engine as engine_module
import javs.scrapers.registry as registry_module
from javs.cli import app
from javs.config import JavsConfig
from javs.models.movie import MovieData
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
        assert "Javlibrary credential chưa đầy đủ" in result.stdout

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
        assert "Javlibrary credential hợp lệ." in result.stdout

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

    def test_find_json_outputs_serialized_movie_data(self, monkeypatch) -> None:
        movie = _movie_data()

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg

            async def find_one(self, movie_id: str, scraper_names=None):
                assert movie_id == "ABP-420"
                assert scraper_names == ["dmm", "r18dev"]
                return movie

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

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
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = []

            async def find_one(self, movie_id: str, scraper_names=None):
                return None

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 1
        assert "No results found for ABP-420" in result.stdout

    def test_find_prints_proxy_failure_summary(self, monkeypatch) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {"kind": "proxy_unreachable", "scraper": "dmm"}
                ]

            async def find_one(self, movie_id: str, scraper_names=None):
                return _movie_data()

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "dmm: proxy unreachable" in result.stdout

    def test_find_prints_translation_provider_warning(self, monkeypatch) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {
                        "kind": "translation_provider_unavailable",
                        "scraper": "translate",
                        "detail": "Install googletrans to enable translation.",
                    }
                ]

            async def find_one(self, movie_id: str, scraper_names=None):
                return _movie_data()

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "translate: translation provider unavailable" in result.stdout
        assert "Install googletrans to enable translation." in result.stdout

    def test_find_prints_translation_config_warning(self, monkeypatch) -> None:
        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg
                self.last_run_diagnostics = [
                    {
                        "kind": "translation_config_invalid",
                        "scraper": "translate",
                        "detail": "DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'.",
                    }
                ]

            async def find_one(self, movie_id: str, scraper_names=None):
                return _movie_data()

        monkeypatch.setattr(config_module, "load_config", lambda _path=None: JavsConfig())
        monkeypatch.setattr(engine_module, "JavsEngine", DummyEngine)

        result = runner.invoke(app, ["find", "ABP-420"])

        assert result.exit_code == 0
        assert "Warnings:" in result.stdout
        assert "translate: translation config invalid" in result.stdout
        assert "DeepL language 'en' is ambiguous; use 'en-us' or 'en-gb'." in result.stdout


class TestCliSortAndScrapers:
    """Test sort command wiring and scraper listing output."""

    def test_sort_passes_flags_to_engine_and_shows_result_table(self, monkeypatch, tmp_path: Path):
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
            ):
                captured.update(
                    {
                        "source": source,
                        "dest": dest,
                        "recurse": recurse,
                        "force": force,
                        "preview": preview,
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
        }
        assert "Sorted 1 files" in result.stdout
        assert "ABP-420" in result.stdout

    def test_sort_update_passes_flags_to_engine_and_shows_result_table(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        class DummyEngine:
            def __init__(self, cfg, cloudflare_recovery_handler=None) -> None:
                self.cfg = cfg

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

            async def sort_path(
                self,
                source: Path,
                dest: Path,
                recurse: bool,
                force: bool,
                preview: bool,
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
