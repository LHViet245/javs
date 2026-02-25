"""Javdb scraper stub."""

from __future__ import annotations

from typing import ClassVar

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


@ScraperRegistry.register
class JavdbScraper(BaseScraper):
    name: ClassVar[str] = "javdb"
    display_name: ClassVar[str] = "JavDB"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://javdb.com"

    async def search(self, movie_id: str) -> str | None:
        return None  # TODO

    async def scrape(self, url: str) -> MovieData | None:
        return None  # TODO


@ScraperRegistry.register
class JavdbZhScraper(JavdbScraper):
    name: ClassVar[str] = "javdbzh"
    display_name: ClassVar[str] = "JavDB (ZH)"
    languages: ClassVar[list[str]] = ["zh"]
