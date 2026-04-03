"""Tests for config sync and template schema alignment."""

from __future__ import annotations

from pathlib import Path

import yaml

from javs.config.models import JavsConfig

TEMPLATE_PATH = Path(__file__).parent.parent / "javs" / "data" / "default_config.yaml"


class TestDefaultConfigTemplate:
    """Ensure the default_config.yaml template matches JavsConfig schema."""

    def test_template_loads_as_valid_config(self) -> None:
        """Template YAML must parse into JavsConfig without validation errors."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        cfg = JavsConfig(**raw)
        assert raw["config_version"] == 1
        assert cfg.config_version == 1
        assert cfg.throttle_limit == 1
        assert cfg.sleep == 2

    def test_template_scrapers_match_schema(self) -> None:
        """Scraper enabled/proxy fields from template must be present in schema."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        cfg = JavsConfig(**raw)
        assert cfg.scrapers.enabled["r18dev"] is True
        assert cfg.scrapers.enabled["dmm"] is True
        assert cfg.scrapers.use_proxy["dmm"] is True
        assert cfg.scrapers.use_proxy["mgstageja"] is True

    def test_template_priority_fields_match(self) -> None:
        """Priority config from template must populate correctly."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        cfg = JavsConfig(**raw)
        assert "r18dev" in cfg.sort.metadata.priority.title
        assert "javlibrary" in cfg.sort.metadata.priority.title

    def test_template_includes_cleanup_empty_source_dir_flag(self) -> None:
        """Template YAML must explicitly ship the cleanup flag with a false value."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        assert raw["sort"]["cleanup_empty_source_dir"] is False

    def test_template_proxy_defaults(self) -> None:
        """Proxy should default to disabled with empty URL."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        cfg = JavsConfig(**raw)
        assert cfg.proxy.enabled is False
        assert cfg.proxy.url == ""

    def test_template_javlibrary_config(self) -> None:
        """Javlibrary config section should be recognized."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        cfg = JavsConfig(**raw)
        assert cfg.javlibrary.base_url == "https://www.javlibrary.com"
        assert cfg.javlibrary.cookie_cf_clearance == ""
        assert cfg.javlibrary.browser_user_agent == ""

    def test_template_no_unknown_top_level_keys(self) -> None:
        """Template should not contain keys that JavsConfig silently ignores."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        valid_fields = set(JavsConfig.model_fields.keys())
        template_keys = set(raw.keys())

        unknown = template_keys - valid_fields
        assert not unknown, f"Unknown top-level keys in template: {unknown}"

    def test_template_excludes_deprecated_placeholder_sections(self) -> None:
        """Template should not advertise config sections with no runtime effect."""
        with open(TEMPLATE_PATH) as f:
            raw = yaml.safe_load(f)

        assert "options" not in raw["scrapers"]
        assert "output_folder" not in raw["sort"]["format"]
        assert "group_actress" not in raw["sort"]["format"]
        assert "tag_csv" not in raw["sort"]["metadata"]
        assert "uncensor_csv" not in raw["locations"]
        assert "history_csv" not in raw["locations"]
        assert "tag_csv" not in raw["locations"]
        assert "javdb" not in raw


class TestSyncUserConfig:
    """Test sync_user_config() with custom paths."""

    def test_sync_creates_new_config(self, tmp_path: Path) -> None:
        """Sync to a new path should create a valid config file."""
        from javs.config.updater import sync_user_config

        target = tmp_path / "config.yaml"
        result = sync_user_config(config_path=target)

        assert result is True
        assert target.exists()

        # Verify the created file is valid
        with open(target) as f:
            raw = yaml.safe_load(f)
        cfg = JavsConfig(**raw)
        assert raw["config_version"] == 1
        assert cfg.config_version == 1
        assert cfg.throttle_limit == 1

    def test_sync_preserves_user_overrides(self, tmp_path: Path) -> None:
        """User overrides should be preserved after sync."""
        from javs.config.updater import sync_user_config

        target = tmp_path / "config.yaml"

        # Create a user config with custom values
        user_config = {"throttle_limit": 5, "sleep": 10}
        with open(target, "w") as f:
            yaml.dump(user_config, f)

        result = sync_user_config(config_path=target)
        assert result is True

        # Verify user values are preserved
        with open(target) as f:
            merged = yaml.safe_load(f)

        assert merged["config_version"] == 1
        assert merged["throttle_limit"] == 5
        assert merged["sleep"] == 10

    def test_sync_removes_deprecated_javlibrary_cookie_keys(self, tmp_path: Path) -> None:
        """Sync should drop deprecated Javlibrary cookie fields from the user config."""
        from javs.config.updater import sync_user_config

        target = tmp_path / "config.yaml"
        with open(target, "w") as f:
            yaml.dump(
                {
                    "javlibrary": {
                        "cookie_cf_clearance": "keep-me",
                        "browser_user_agent": "keep-me-too",
                        "cookie_cf_bm": "drop-me",
                        "cookie_session": "drop-me",
                        "cookie_userid": "drop-me",
                    },
                    "check_updates": True,
                },
                f,
            )

        result = sync_user_config(config_path=target)
        assert result is True

        with open(target) as f:
            merged = yaml.safe_load(f)

        assert merged["javlibrary"]["cookie_cf_clearance"] == "keep-me"
        assert merged["javlibrary"]["browser_user_agent"] == "keep-me-too"
        assert "cookie_cf_bm" not in merged["javlibrary"]
        assert "cookie_session" not in merged["javlibrary"]
        assert "cookie_userid" not in merged["javlibrary"]
        assert "check_updates" not in merged

    def test_sync_removes_deprecated_sort_flags(self, tmp_path: Path) -> None:
        """Sync should drop deprecated sort flags that no longer affect runtime."""
        from javs.config.updater import sync_user_config

        target = tmp_path / "config.yaml"
        with open(target, "w") as f:
            yaml.dump(
                {
                    "sort": {
                        "rename_file": True,
                        "rename_folder_in_place": True,
                    }
                },
                f,
            )

        result = sync_user_config(config_path=target)
        assert result is True

        with open(target) as f:
            merged = yaml.safe_load(f)

        assert merged["sort"]["rename_file"] is True
        assert "rename_folder_in_place" not in merged["sort"]

    def test_sync_removes_deprecated_placeholder_sections(self, tmp_path: Path) -> None:
        """Sync should prune config sections that are still public but unused at runtime."""
        from javs.config.updater import sync_user_config

        target = tmp_path / "config.yaml"
        with open(target, "w") as f:
            yaml.dump(
                {
                    "scrapers": {
                        "enabled": {"dmm": True},
                        "options": {"id_preference": "contentid"},
                    },
                    "sort": {
                        "format": {
                            "file": "{id}",
                            "output_folder": "unused",
                            "group_actress": True,
                        },
                        "metadata": {
                            "tag_csv": {
                                "enabled": True,
                                "auto_add": True,
                            }
                        },
                    },
                    "locations": {
                        "thumb_csv": "/tmp/thumbs.csv",
                        "uncensor_csv": "/tmp/uncensor.csv",
                        "history_csv": "/tmp/history.csv",
                        "tag_csv": "/tmp/tags.csv",
                    },
                    "javdb": {"session": "legacy"},
                },
                f,
            )

        result = sync_user_config(config_path=target)
        assert result is True

        with open(target) as f:
            merged = yaml.safe_load(f)

        assert "options" not in merged["scrapers"]
        assert "output_folder" not in merged["sort"]["format"]
        assert "group_actress" not in merged["sort"]["format"]
        assert "tag_csv" not in merged["sort"]["metadata"]
        assert "thumb_csv" in merged["locations"]
        assert "uncensor_csv" not in merged["locations"]
        assert "history_csv" not in merged["locations"]
        assert "tag_csv" not in merged["locations"]
        assert "javdb" not in merged
