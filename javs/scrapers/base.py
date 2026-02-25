"""Abstract base class for all scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from javs.models.movie import MovieData
from javs.services.http import HttpClient
from javs.utils.logging import get_logger


class BaseScraper(ABC):
    """Abstract base class that all scraper plugins must implement.

    Each scraper targets a single data source (e.g., DMM, Javlibrary)
    and knows how to search for a movie ID and scrape its metadata.
    """

    # Class-level metadata — override in subclasses
    name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    languages: ClassVar[list[str]] = []
    base_url: ClassVar[str] = ""

    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()
        self.logger = get_logger(f"scraper.{self.name}")

    @abstractmethod
    async def search(self, movie_id: str) -> str | None:
        """Find the URL for a given movie ID.

        Args:
            movie_id: JAV movie ID (e.g., "ABP-420").

        Returns:
            Full URL to the movie page, or None if not found.
        """

    @abstractmethod
    async def scrape(self, url: str) -> MovieData | None:
        """Scrape movie metadata from a URL.

        Args:
            url: Full URL to the movie detail page.

        Returns:
            Populated MovieData, or None if scraping failed.
        """

    async def search_and_scrape(self, movie_id: str) -> MovieData | None:
        """Convenience: search for ID then scrape the result.

        Args:
            movie_id: JAV movie ID.

        Returns:
            MovieData or None.
        """
        try:
            url = await self.search(movie_id)
            if not url:
                self.logger.debug("search_no_result", movie_id=movie_id)
                return None

            data = await self.scrape(url)
            if data:
                data.source = self.name
            return data
        except Exception as exc:
            self.logger.error(
                "scraper_error",
                movie_id=movie_id,
                scraper=self.name,
                error=str(exc),
            )
            return None

    @staticmethod
    def normalize_id(movie_id: str) -> str:
        """Normalize a movie ID to standard format (ABC-123).

        Handles various input formats:
        - abc123 → ABC-123
        - ABC123 → ABC-123
        - ABC-0123 → ABC-123

        Args:
            movie_id: Raw movie ID string.

        Returns:
            Normalized ID.
        """
        import re

        movie_id = movie_id.strip().upper()

        # Already has a dash
        if "-" in movie_id:
            parts = movie_id.split("-", 1)
            prefix = parts[0]
            number = parts[1].lstrip("0") or "0"
            number = number.zfill(3)
            return f"{prefix}-{number}"

        # No dash — split letters from numbers
        match = re.match(r"([A-Z]+)(\d+)", movie_id)
        if match:
            prefix = match.group(1)
            number = match.group(2).lstrip("0") or "0"
            number = number.zfill(3)
            return f"{prefix}-{number}"

        return movie_id

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
