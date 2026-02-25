"""R18.dev scraper — JSON API-based metadata fetcher.

Replaces Javinizer's:
  - Scraper.R18dev.ps1 (337 lines)
  - Get-R18DevUrl.ps1 (76 lines)
  - Get-R18DevData.ps1 (66 lines)

R18.dev exposes a clean JSON API, so no HTML parsing is needed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, ClassVar

from javs.models.movie import Actress, MovieData
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry
from javs.utils.logging import get_logger
from javs.utils.string import clean_title

logger = get_logger(__name__)

# Custom user agent matching the original Javinizer
R18_USER_AGENT = "javs (+https://github.com/javs)"

# Base API endpoint
R18_API_BASE = "https://r18.dev/videos/vod/movies/detail/-"


@ScraperRegistry.register
class R18DevScraper(BaseScraper):
    """Scraper for R18.dev using its JSON API.

    R18.dev provides a REST-like JSON API:
      - Search by dvd_id:  /dvd_id={ID}/json
      - Detail by combined: /combined={content_id}/json

    All metadata is returned as structured JSON — no HTML parsing needed.
    """

    name: ClassVar[str] = "r18dev"
    display_name: ClassVar[str] = "R18.dev"
    languages: ClassVar[list[str]] = ["en"]
    base_url: ClassVar[str] = "https://r18.dev"

    async def search(self, movie_id: str) -> str | None:
        """Search R18.dev by DVD ID.

        The API flow:
        1. GET /dvd_id={movie_id}/json → get content_id
        2. Build detail URL: /combined={content_id}/json

        Args:
            movie_id: JAV movie ID (e.g., "ABP-420").

        Returns:
            API detail URL, or None if not found.
        """
        normalized = self.normalize_id(movie_id)
        search_url = f"{R18_API_BASE}/dvd_id={normalized}/json"

        try:
            data = await self.http.get_json(
                search_url,
                headers={"User-Agent": R18_USER_AGENT},
            )
        except Exception as exc:
            self.logger.debug("r18dev_search_error", movie_id=normalized, error=str(exc))
            return None

        if not data or not isinstance(data, dict):
            return None

        content_id = data.get("content_id")
        if not content_id:
            self.logger.debug("r18dev_no_content_id", movie_id=normalized)
            return None

        # Build the detail URL using combined= for full data
        detail_url = f"{R18_API_BASE}/combined={content_id}/json"

        # Verify the result matches our search ID
        result_dvd_id = data.get("dvd_id", "")
        if result_dvd_id and result_dvd_id.upper() != normalized.upper():
            self.logger.debug(
                "r18dev_id_mismatch",
                expected=normalized,
                got=result_dvd_id,
            )
            return None

        return detail_url

    async def scrape(self, url: str) -> MovieData | None:
        """Scrape movie metadata from R18.dev JSON API.

        Args:
            url: Full API URL (combined= or dvd_id=).

        Returns:
            Populated MovieData, or None.
        """
        try:
            data = await self.http.get_json(
                url,
                headers={"User-Agent": R18_USER_AGENT},
            )
        except Exception as exc:
            self.logger.error("r18dev_scrape_error", url=url, error=str(exc))
            return None

        if not data or not isinstance(data, dict):
            self.logger.warning("r18dev_empty_response", url=url)
            return None

        return self._parse_json(data)

    def _parse_json(self, data: dict[str, Any]) -> MovieData:
        """Parse the R18.dev JSON response into MovieData.

        The JSON structure has direct fields like:
        dvd_id, content_id, title_en, title_ja, comment_en,
        release_date, runtime_mins, maker_name_en, etc.

        Args:
            data: Parsed JSON response dict.

        Returns:
            MovieData populated from the JSON.
        """
        return MovieData(
            id=data.get("dvd_id", ""),
            content_id=data.get("content_id"),
            title=self._parse_title(data),
            alternate_title=self._parse_title_ja(data),
            description=self._parse_description(data),
            release_date=self._parse_release_date(data),
            runtime=self._parse_runtime(data),
            director=self._parse_director(data),
            maker=self._parse_maker(data),
            label=self._parse_label(data),
            series=self._parse_series(data),
            genres=self._parse_genres(data),
            actresses=self._parse_actresses(data),
            cover_url=self._parse_cover_url(data),
            screenshot_urls=self._parse_screenshot_urls(data),
            trailer_url=self._parse_trailer_url(data),
            source=self.name,
        )

    # ─── Field Parsers ───────────────────────────────────────

    @staticmethod
    def _parse_title(data: dict) -> str | None:
        """Extract English title, falling back to generic title."""
        title = data.get("title_en") or data.get("title")
        return clean_title(title) if title else None

    @staticmethod
    def _parse_title_ja(data: dict) -> str | None:
        """Extract Japanese title."""
        title = data.get("title_ja")
        return clean_title(title) if title else None

    @staticmethod
    def _parse_description(data: dict) -> str | None:
        """Extract English description/comment."""
        desc = data.get("comment_en")
        return clean_title(desc) if desc else None

    @staticmethod
    def _parse_release_date(data: dict) -> date | None:
        """Parse release_date field (format: 'YYYY-MM-DD HH:MM:SS')."""
        raw = data.get("release_date")
        if not raw:
            return None

        # Take only the date part before any space
        date_str = raw.split(" ")[0] if " " in raw else raw
        try:
            parts = date_str.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_runtime(data: dict) -> int | None:
        """Extract runtime in minutes."""
        runtime = data.get("runtime_mins")
        if runtime is not None:
            try:
                return int(runtime)
            except (ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _parse_director(data: dict) -> str | None:
        """Extract director name (first one, romaji)."""
        directors = data.get("directors")
        if directors and isinstance(directors, list) and len(directors) > 0:
            return directors[0].get("name_romaji") or directors[0].get("name_kanji")
        return None

    @staticmethod
    def _parse_maker(data: dict) -> str | None:
        """Extract studio/maker name."""
        maker = data.get("maker_name_en")
        if maker:
            return clean_title(maker.replace("\\n", " "))
        return None

    @staticmethod
    def _parse_label(data: dict) -> str | None:
        """Extract label name."""
        label = data.get("label_name_en")
        if label:
            return clean_title(label.replace("\\n", " "))
        return None

    @staticmethod
    def _parse_series(data: dict) -> str | None:
        """Extract series name."""
        return data.get("series_name_en") or None

    @staticmethod
    def _parse_genres(data: dict) -> list[str]:
        """Extract genre/category names (English)."""
        categories = data.get("categories")
        if not categories or not isinstance(categories, list):
            return []

        genres = []
        for cat in categories:
            name = cat.get("name_en")
            if name:
                genres.append(clean_title(name))
        return genres

    @staticmethod
    def _parse_actresses(data: dict) -> list[Actress]:
        """Parse actress data from the actresses array.

        Each actress object has:
          - name_romaji: "FirstName LastName"
          - name_kanji: Japanese name (may include aliases in parentheses)
          - image_url: thumbnail path or full URL
        """
        actresses_raw = data.get("actresses")
        if not actresses_raw or not isinstance(actresses_raw, list):
            return []

        result = []
        for actress_data in actresses_raw:
            romaji = actress_data.get("name_romaji", "")
            kanji = actress_data.get("name_kanji", "")

            # Parse romaji name: "FirstName LastName"
            first_name = None
            last_name = None
            if romaji:
                romaji = romaji.replace("\\", "").strip()
                parts = romaji.split(" ", 1)
                if len(parts) >= 2:
                    first_name = parts[0].strip()
                    last_name = parts[1].strip()
                elif len(parts) == 1:
                    first_name = parts[0].strip()

            # Clean up Japanese name — remove aliases in parentheses
            japanese_name = None
            if kanji:
                japanese_name = re.sub(r"（.*）", "", kanji).replace("&amp;", "&").strip()

            # Build thumbnail URL
            thumb_url = actress_data.get("image_url")
            if thumb_url and not thumb_url.startswith("http"):
                thumb_url = f"https://pics.dmm.co.jp/mono/actjpgs/{thumb_url}"

            result.append(
                Actress(
                    last_name=last_name,
                    first_name=first_name,
                    japanese_name=japanese_name or None,
                    thumb_url=thumb_url or None,
                )
            )

        return result

    @staticmethod
    def _parse_cover_url(data: dict) -> str | None:
        """Extract cover/jacket image URL."""
        url = data.get("jacket_full_url")
        if url:
            # Ensure we get the large version
            return url.replace("ps.jpg", "pl.jpg")
        return None

    @staticmethod
    def _parse_screenshot_urls(data: dict) -> list[str]:
        """Extract screenshot gallery URLs."""
        gallery = data.get("gallery")
        if not gallery or not isinstance(gallery, dict):
            return []

        # Prefer full-size images, fallback to thumbnails
        images = gallery.get("image_full") or gallery.get("image_thumb")
        if not images or not isinstance(images, list):
            return []

        # Convert thumbnail URLs to full-size (same as original Javinizer)
        result = []
        for url in images:
            if url:
                # Replace '-' with 'jp-' but not if already starts with 'jp-'
                converted = re.sub(r"(?<!jp)-", "jp-", url)
                result.append(converted)
        return result

    @staticmethod
    def _parse_trailer_url(data: dict) -> str | None:
        """Extract sample/trailer video URL."""
        return data.get("sample_url") or None
