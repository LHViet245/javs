"""Aventertainment scraper stub."""

from __future__ import annotations

from typing import ClassVar

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


@ScraperRegistry.register
class AventertainmentScraper(BaseScraper):
    name: ClassVar[str] = "aventertainment"
    display_name: ClassVar[str] = "Aventertainment"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://www.aventertainments.com"

    async def search(self, movie_id: str) -> str | None:
        return None  # TODO

    async def scrape(self, url: str) -> MovieData | None:
        return None  # TODO


@ScraperRegistry.register
class AventertainmentJaScraper(AventertainmentScraper):
    name: ClassVar[str] = "aventertainmentja"
    display_name: ClassVar[str] = "Aventertainment (JA)"
    languages: ClassVar[list[str]] = ["ja"]
