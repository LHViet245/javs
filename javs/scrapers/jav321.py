"""Jav321 scraper stub."""

from __future__ import annotations

from typing import ClassVar

from javs.models.movie import MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry


@ScraperRegistry.register
class Jav321JaScraper(BaseScraper):
    name: ClassVar[str] = "jav321ja"
    display_name: ClassVar[str] = "Jav321 (JA)"
    languages: ClassVar[list[str]] = ["ja"]
    base_url: ClassVar[str] = "https://www.jav321.com"

    async def search(self, movie_id: str) -> str | None:
        return None  # TODO

    async def scrape(self, url: str) -> MovieData | None:
        return None  # TODO
