"""Tests for scraper registry behavior."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import javs.scrapers.registry as registry_module
from javs.config.models import ProxyConfig, ScraperConfig
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


class _DummyScraper(BaseScraper):
    name = "dummy"
    display_name = "Dummy"
    languages = ["en"]
    base_url = "https://example.com"

    async def search(self, movie_id: str) -> str | None:
        del movie_id
        return None

    async def scrape(self, url: str):
        del url
        return None


class _OtherScraper(BaseScraper):
    name = "other"
    display_name = "Other"
    languages = ["en"]
    base_url = "https://example.com"

    async def search(self, movie_id: str) -> str | None:
        del movie_id
        return None

    async def scrape(self, url: str):
        del url
        return None


@pytest.fixture(autouse=True)
def _restore_registry() -> None:
    original = dict(ScraperRegistry._scrapers)
    ScraperRegistry._scrapers.clear()
    try:
        yield
    finally:
        ScraperRegistry._scrapers.clear()
        ScraperRegistry._scrapers.update(original)


def _logger_spy() -> SimpleNamespace:
    return SimpleNamespace(debug=MagicMock(), warning=MagicMock())


def test_register_requires_name() -> None:
    class NamelessScraper(BaseScraper):
        name = ""
        display_name = "Nameless"
        languages = ["en"]
        base_url = "https://example.com"

        async def search(self, movie_id: str) -> str | None:
            del movie_id
            return None

        async def scrape(self, url: str):
            del url
            return None

    with pytest.raises(ValueError, match="must have a 'name' class variable"):
        ScraperRegistry.register(NamelessScraper)


def test_get_all_get_and_list_names_return_registered_scrapers() -> None:
    ScraperRegistry.register(_DummyScraper)

    all_scrapers = ScraperRegistry.get_all()

    assert all_scrapers == {"dummy": _DummyScraper}
    assert ScraperRegistry.get("dummy") is _DummyScraper
    assert ScraperRegistry.list_names() == ["dummy"]

    all_scrapers["other"] = _OtherScraper
    assert ScraperRegistry.get("other") is None


def test_get_enabled_applies_proxy_routing_and_warns_for_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ScraperRegistry.register(_DummyScraper)
    ScraperRegistry.register(_OtherScraper)

    logger = _logger_spy()
    monkeypatch.setattr(registry_module, "logger", logger)

    config = ScraperConfig(
        enabled={"dummy": True, "other": True, "ghost": True},
        use_proxy={"dummy": True, "other": False, "ghost": True},
    )
    proxy_config = ProxyConfig(enabled=True, url="http://1.2.3.4:8080")
    http = object()

    scrapers = ScraperRegistry.get_enabled(config, http=http, proxy_config=proxy_config)

    assert [scraper.name for scraper in scrapers] == ["dummy", "other"]
    assert scrapers[0].http is http
    assert scrapers[0].use_proxy is True
    assert scrapers[1].http is http
    assert scrapers[1].use_proxy is False
    logger.warning.assert_called_once_with("scraper_not_found", name="ghost")


def test_get_by_names_applies_proxy_routing_and_warns_for_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ScraperRegistry.register(_DummyScraper)
    ScraperRegistry.register(_OtherScraper)

    logger = _logger_spy()
    monkeypatch.setattr(registry_module, "logger", logger)

    config = ScraperConfig(
        use_proxy={"dummy": True, "other": False, "ghost": True},
    )
    proxy_config = ProxyConfig(enabled=True, url="http://1.2.3.4:8080")
    http = object()

    scrapers = ScraperRegistry.get_by_names(
        ["other", "ghost", "dummy"],
        http=http,
        config=config,
        proxy_config=proxy_config,
    )

    assert [scraper.name for scraper in scrapers] == ["other", "dummy"]
    assert scrapers[0].http is http
    assert scrapers[0].use_proxy is False
    assert scrapers[1].http is http
    assert scrapers[1].use_proxy is True
    logger.warning.assert_called_once_with("scraper_not_found", name="ghost")


def test_load_all_logs_import_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = _logger_spy()
    monkeypatch.setattr(registry_module, "logger", logger)

    attempted: list[str] = []

    def fake_import_module(module_name: str):
        attempted.append(module_name)
        if module_name == "javs.scrapers.javlibrary":
            raise ImportError("boom")
        return SimpleNamespace(__name__=module_name)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    ScraperRegistry.load_all()

    assert attempted == [
        "javs.scrapers.dmm",
        "javs.scrapers.r18dev",
        "javs.scrapers.javlibrary",
        "javs.scrapers.mgstage",
    ]
    logger.debug.assert_called_once_with(
        "scraper_module_not_found",
        module="javs.scrapers.javlibrary",
    )
