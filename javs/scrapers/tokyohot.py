"""TokyoHot scraper stub."""

from __future__ import annotations

from typing import ClassVar

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


@ScraperRegistry.register
class TokyoHotScraper(BaseScraper):
    name: ClassVar[str] = "tokyohot"
    display_name: ClassVar[str] = "TokyoHot"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://my.tokyo-hot.com"

    async def search(self, movie_id: str) -> str | None:
        return None  # TODO

    async def scrape(self, url: str) -> MovieData | None:
        return None  # TODO


@ScraperRegistry.register
class TokyoHotJaScraper(TokyoHotScraper):
    name: ClassVar[str] = "tokyohotja"
    display_name: ClassVar[str] = "TokyoHot (JA)"
    languages: ClassVar[list[str]] = ["ja"]


@ScraperRegistry.register
class TokyoHotZhScraper(TokyoHotScraper):
    name: ClassVar[str] = "tokyohotzh"
    display_name: ClassVar[str] = "TokyoHot (ZH)"
    languages: ClassVar[list[str]] = ["zh"]
