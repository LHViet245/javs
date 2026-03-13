"""Tests for configuration system."""

import yaml

from javs.config import JavsConfig, create_default_config, load_config, save_config


class TestJavsConfig:
    """Test JavsConfig Pydantic model."""

    def test_default_config(self):
        """Default config should be valid."""
        config = JavsConfig()
        assert config.throttle_limit == 1
        assert config.sleep == 3
        assert config.scrapers.enabled["r18dev"] is True

    def test_default_config_scrapers(self) -> None:
        config = JavsConfig()
        assert config.scrapers.enabled["dmm"] is True
        assert config.scrapers.enabled["javlibrary"] is False

    def test_match_defaults(self):
        """Match config should have sensible defaults."""
        config = JavsConfig()
        assert ".mp4" in config.match.included_extensions
        assert ".mkv" in config.match.included_extensions
        assert config.match.minimum_file_size_mb == 0

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
        assert config.sleep == 3  # default
