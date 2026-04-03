"""Tests for BaseScraper helpers and orchestration."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper


class _DummyScraper(BaseScraper):
    name = "dummy"
    display_name = "Dummy"
    languages = ["en"]
    base_url = "https://example.com"

    def __init__(self, http=None, use_proxy: bool = False) -> None:
        super().__init__(http=http, use_proxy=use_proxy)
        self.search_calls: list[str] = []
        self.scrape_calls: list[str] = []
        self.search_result: str | None = None
        self.scrape_result: MovieData | None = None
        self.search_error: Exception | None = None
        self.scrape_error: Exception | None = None

    async def search(self, movie_id: str) -> str | None:
        self.search_calls.append(movie_id)
        if self.search_error:
            raise self.search_error
        return self.search_result

    async def scrape(self, url: str) -> MovieData | None:
        self.scrape_calls.append(url)
        if self.scrape_error:
            raise self.scrape_error
        return self.scrape_result


@pytest.mark.parametrize(
    ("movie_id", "expected"),
    [
        ("abc123", "ABC-123"),
        ("ABC123", "ABC-123"),
        ("ABC-0123", "ABC-123"),
        ("ABP-1", "ABP-001"),
        ("abp-000", "ABP-000"),
        ("START-539", "START-539"),
        ("UNCHANGED", "UNCHANGED"),
    ],
)
def test_normalize_id(movie_id: str, expected: str) -> None:
    assert BaseScraper.normalize_id(movie_id) == expected


@pytest.mark.asyncio
async def test_search_and_scrape_success_sets_source() -> None:
    scraper = _DummyScraper(http=object())
    scraper.search_result = "https://example.com/movie"
    scraper.scrape_result = MovieData(
        id="ABP-420",
        title="Test Movie",
        release_date=date(2023, 6, 15),
    )
    scraper.logger = SimpleNamespace(debug=MagicMock(), error=MagicMock())

    result = await scraper.search_and_scrape("ABP-420")

    assert result is scraper.scrape_result
    assert result is not None
    assert result.source == "dummy"
    assert scraper.search_calls == ["ABP-420"]
    assert scraper.scrape_calls == ["https://example.com/movie"]


@pytest.mark.asyncio
async def test_search_and_scrape_no_result_skips_scrape_and_logs_debug() -> None:
    debug_mock = MagicMock()
    error_mock = MagicMock()
    scraper = _DummyScraper(http=object())
    scraper.search_result = None
    scraper.logger = SimpleNamespace(debug=debug_mock, error=error_mock)

    result = await scraper.search_and_scrape("ABP-420")

    assert result is None
    assert scraper.search_calls == ["ABP-420"]
    assert scraper.scrape_calls == []
    debug_mock.assert_called_once_with("search_no_result", movie_id="ABP-420")
    error_mock.assert_not_called()


@pytest.mark.asyncio
async def test_search_and_scrape_exception_logs_error_and_returns_none() -> None:
    error_mock = MagicMock()
    scraper = _DummyScraper(http=object())
    scraper.search_result = "https://example.com/movie"
    scraper.scrape_error = RuntimeError("boom")
    scraper.logger = SimpleNamespace(debug=MagicMock(), error=error_mock)

    result = await scraper.search_and_scrape("ABP-420")

    assert result is None
    assert scraper.search_calls == ["ABP-420"]
    assert scraper.scrape_calls == ["https://example.com/movie"]
    error_mock.assert_called_once_with(
        "scraper_error",
        movie_id="ABP-420",
        scraper="dummy",
        error="boom",
    )
