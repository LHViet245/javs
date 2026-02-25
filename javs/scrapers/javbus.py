"""Javbus scraper stub."""

from __future__ import annotations

from typing import ClassVar

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


@ScraperRegistry.register
class JavbusScraper(BaseScraper):
    name: ClassVar[str] = "javbus"
    display_name: ClassVar[str] = "JavBus"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://www.javbus.com"

    async def search(self, movie_id: str) -> str | None:
        return None  # TODO

    async def scrape(self, url: str) -> MovieData | None:
        return None  # TODO


@ScraperRegistry.register
class JavbusJaScraper(JavbusScraper):
    name: ClassVar[str] = "javbusja"
    display_name: ClassVar[str] = "JavBus (JA)"
    languages: ClassVar[list[str]] = ["ja"]


@ScraperRegistry.register
class JavbusZhScraper(JavbusScraper):
    name: ClassVar[str] = "javbuszh"
    display_name: ClassVar[str] = "JavBus (ZH)"
    languages: ClassVar[list[str]] = ["zh"]
