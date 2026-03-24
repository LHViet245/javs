"""Tests for configuration system."""

from pathlib import Path

import yaml

from javs.config import (
    JavsConfig,
    create_default_config,
    load_config,
    redact_config_for_display,
    save_config,
)


class TestJavsConfig:
    """Test JavsConfig Pydantic model."""

    def test_default_config(self):
        """Default config should be valid."""
        config = JavsConfig()
        assert config.throttle_limit == 1
        assert config.sleep == 2
        assert config.scrapers.enabled["r18dev"] is True

    def test_default_config_scrapers(self) -> None:
        config = JavsConfig()
        assert config.scrapers.enabled["dmm"] is True
        assert config.scrapers.enabled["javlibrary"] is False

    def test_match_defaults(self):
        """Match config should have sensible defaults."""
        config = JavsConfig()
        assert config.match.mode == "auto"
        assert ".mp4" in config.match.included_extensions
        assert ".mkv" in config.match.included_extensions
        assert config.match.minimum_file_size_mb == 0

    def test_legacy_regex_enabled_promotes_match_mode_to_custom(self, tmp_path: Path):
        path = tmp_path / "legacy-regex.yaml"
        path.write_text(
            yaml.dump(
                {
                    "match": {
                        "regex_enabled": True,
                        "regex": {
                            "pattern": "([A-Z]+-\\d+)",
                            "id_match_group": 1,
                            "part_match_group": 2,
                        },
                    }
                }
            )
        )

        config = load_config(path)

        assert config.match.mode == "custom"
        assert config.match.regex_enabled is True

    def test_sort_format_defaults(self):
        """Sort format templates should match Javinizer defaults."""
        config = JavsConfig()
        assert "{id}" in config.sort.format.file
        assert "{id}" in config.sort.format.folder

    def test_priority_defaults(self):
        """Priority lists should have valid scraper names."""
        config = JavsConfig()
        assert "r18dev" in config.sort.metadata.priority.title

    def test_default_priority(self) -> None:
        config = JavsConfig()
        assert "dmm" in config.sort.metadata.priority.actress
        assert config.sort.metadata.priority.title[0] == "r18dev"

    def test_translate_affect_sort_names_defaults_to_false(self) -> None:
        config = JavsConfig()

        assert config.sort.metadata.nfo.translate.affect_sort_names is False

    def test_translate_language_defaults_to_en_us(self) -> None:
        config = JavsConfig()

        assert config.sort.metadata.nfo.translate.language == "en-us"

    def test_redact_config_for_display_masks_sensitive_values(self) -> None:
        config = JavsConfig()
        config.sort.metadata.nfo.translate.deepl_api_key = "super-secret-deepl-key"
        config.proxy.url = "http://user:pass@example.com:8080"
        config.javlibrary.cookie_cf_clearance = "cf-secret"

        safe = redact_config_for_display(config)

        assert safe["sort"]["metadata"]["nfo"]["translate"]["deepl_api_key"] == "***"
        assert safe["proxy"]["url"] == "http://***:***@example.com:8080"
        assert safe["javlibrary"]["cookie_cf_clearance"] == "***"

    def test_serialization_roundtrip(self, tmp_path):
        """Config should survive save/load roundtrip."""
        config = JavsConfig()
        config.throttle_limit = 5
        config.sleep = 10

        path = tmp_path / "config.yaml"
        save_config(config, path)

        loaded = load_config(path)
        assert loaded.throttle_limit == 5
        assert loaded.sleep == 10

    def test_translate_affect_sort_names_survives_save_load_roundtrip(
        self,
        tmp_path: Path,
    ) -> None:
        config = JavsConfig()
        config.sort.metadata.nfo.translate.affect_sort_names = True

        path = tmp_path / "config.yaml"
        save_config(config, path)

        loaded = load_config(path)

        assert loaded.sort.metadata.nfo.translate.affect_sort_names is True

    def test_save_config_preserves_existing_comments(self, tmp_path: Path) -> None:
        """Saving an existing config should not strip explanatory comments."""
        path = tmp_path / "config.yaml"
        path.write_text(
            (
                "# top level comment\n"
                "javlibrary:\n"
                "  # keep this explanation\n"
                "  browser_user_agent: \"\"\n"
                "  cookie_cf_clearance: \"\"\n"
            ),
            encoding="utf-8",
        )

        config = load_config(path)
        config.javlibrary.cookie_cf_clearance = "new-cookie"

        save_config(config, path)

        saved = path.read_text(encoding="utf-8")
        assert "# keep this explanation" in saved
        assert 'cookie_cf_clearance: "new-cookie"' in saved

    def test_load_nonexistent_returns_default(self, tmp_path):
        """Loading from nonexistent path should return defaults."""
        config = load_config(tmp_path / "does_not_exist.yaml")
        assert config.throttle_limit == 1

    def test_create_default_config(self, tmp_path):
        """create_default_config should create a file and return config."""
        path = tmp_path / "new_config.yaml"
        config = create_default_config(path)
        assert path.exists()
        assert isinstance(config, JavsConfig)

    def test_partial_yaml_load(self, tmp_path):
        """Loading YAML with partial keys should fill in defaults."""
        path = tmp_path / "partial.yaml"
        path.write_text(yaml.dump({"throttle_limit": 10}))

        config = load_config(path)
        assert config.throttle_limit == 10
        assert config.sleep == 2  # default

    def test_deprecated_javlibrary_cookie_keys_are_ignored(self, tmp_path: Path):
        """Deprecated Javlibrary cookie fields should no longer affect the config model."""
        path = tmp_path / "deprecated.yaml"
        path.write_text(
            yaml.dump(
                {
                    "javlibrary": {
                        "cookie_cf_bm": "legacy-bm",
                        "cookie_session": "legacy-session",
                        "cookie_userid": "legacy-userid",
                        "cookie_cf_clearance": "kept",
                    }
                }
            )
        )

        config = load_config(path)

        assert config.javlibrary.cookie_cf_clearance == "kept"
        assert not hasattr(config.javlibrary, "cookie_cf_bm")
        assert not hasattr(config.javlibrary, "cookie_session")
        assert not hasattr(config.javlibrary, "cookie_userid")

    def test_deprecated_placeholder_sections_are_ignored(self, tmp_path: Path) -> None:
        """Deprecated placeholder sections should no longer surface on the model."""
        path = tmp_path / "deprecated-placeholders.yaml"
        path.write_text(
            yaml.dump(
                {
                    "scrapers": {
                        "options": {
                            "id_preference": "contentid",
                            "add_male_actors": True,
                            "dmm_scrape_actress": True,
                        }
                    },
                    "sort": {
                        "format": {
                            "output_folder": "unused",
                            "group_actress": False,
                        },
                        "metadata": {
                            "tag_csv": {
                                "enabled": True,
                                "auto_add": True,
                            }
                        },
                    },
                    "locations": {
                        "uncensor_csv": "/tmp/uncensor.csv",
                        "history_csv": "/tmp/history.csv",
                        "tag_csv": "/tmp/tags.csv",
                    },
                    "javdb": {"session": "legacy"},
                }
            )
        )

        config = load_config(path)

        assert not hasattr(config.scrapers, "options")
        assert not hasattr(config.sort.format, "output_folder")
        assert not hasattr(config.sort.format, "group_actress")
        assert not hasattr(config.sort.metadata, "tag_csv")
        assert not hasattr(config.locations, "uncensor_csv")
        assert not hasattr(config.locations, "history_csv")
        assert not hasattr(config.locations, "tag_csv")
        assert not hasattr(config, "javdb")

    def test_init_csv_templates_creates_user_local_templates(self, tmp_path: Path) -> None:
        from javs.config.csv_templates import init_csv_templates

        config = JavsConfig()
        config_path = tmp_path / "config.yaml"

        result = init_csv_templates(config, config_path)

        assert result.genre_csv_path.exists()
        assert result.thumb_csv_path.exists()
        assert result.genre_csv_path.read_text(encoding="utf-8-sig").startswith(
            "Original,Replacement"
        )
        assert result.thumb_csv_path.read_text(encoding="utf-8-sig").startswith(
            "FullName,JapaneseName,ThumbUrl"
        )

        loaded = load_config(config_path)
        assert loaded.locations.genre_csv == str(result.genre_csv_path)
        assert loaded.locations.thumb_csv == str(result.thumb_csv_path)
