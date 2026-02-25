"""Data aggregator: merges metadata from multiple scrapers by priority.

Replaces Javinizer's Get-JVAggregatedData.ps1 (891 lines).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from javs.config.models import JavsConfig
from javs.models.movie import MovieData
from javs.utils.logging import get_logger
from javs.utils.string import clean_title, format_template

logger = get_logger(__name__)


class DataAggregator:
    """Merge metadata from multiple scrapers using priority-based selection.

    For each metadata field, the aggregator checks sources in the priority
    order defined in config and uses the first non-empty value.
    """

    def __init__(self, config: JavsConfig) -> None:
        self.config = config
        self._genre_map: dict[str, str] | None = None
        self._genre_ignore: list[re.Pattern] | None = None
        self._thumb_cache: dict[str, str] | None = None

    def merge(self, results: list[MovieData]) -> MovieData:
        """Merge multiple MovieData objects into one based on priority.

        Args:
            results: List of MovieData from different scrapers.

        Returns:
            A single merged MovieData.
        """
        if not results:
            return MovieData()

        if len(results) == 1:
            merged = results[0].model_copy(deep=True)
            self._post_process(merged)
            return merged

        source_map: dict[str, MovieData] = {}
        for r in results:
            if r.source:
                source_map[r.source] = r

        priority = self.config.sort.metadata.priority
        merged = MovieData()

        # Merge each field by priority
        merged.id = self._pick_field(source_map, priority.id, "id")
        merged.content_id = self._pick_field(source_map, priority.content_id, "content_id")
        merged.title = self._pick_field(source_map, priority.title, "title")
        merged.alternate_title = self._pick_field(
            source_map, priority.alternate_title, "alternate_title"
        )
        merged.description = self._pick_field(source_map, priority.description, "description")
        merged.director = self._pick_field(source_map, priority.director, "director")
        merged.maker = self._pick_field(source_map, priority.maker, "maker")
        merged.label = self._pick_field(source_map, priority.label, "label")
        merged.series = self._pick_field(source_map, priority.series, "series")
        merged.runtime = self._pick_field(source_map, priority.runtime, "runtime")
        merged.trailer_url = self._pick_field(source_map, priority.trailer_url, "trailer_url")

        # Date
        merged.release_date = self._pick_field(source_map, priority.release_date, "release_date")

        # Rating (object, not scalar)
        merged.rating = self._pick_field(source_map, priority.rating, "rating")

        # Cover URL
        merged.cover_url = self._pick_field(source_map, priority.cover_url, "cover_url")

        # Screenshot URLs (merge all unique)
        merged.screenshot_urls = self._pick_field(
            source_map, priority.screenshot_url, "screenshot_urls"
        )

        # Lists: genres, actresses
        merged.genres = self._pick_list_field(source_map, priority.genre, "genres")
        merged.actresses = self._pick_list_field(source_map, priority.actress, "actresses")

        # Post-process
        self._post_process(merged)

        return merged

    def _pick_field(self, source_map: dict[str, MovieData], priority: list[str], field: str):
        """Pick the first non-empty value from sources in priority order."""
        for source_name in priority:
            if source_name in source_map:
                value = getattr(source_map[source_name], field, None)
                if value is not None and value != "" and value != []:
                    return value
        # Fallback: try any source
        for data in source_map.values():
            value = getattr(data, field, None)
            if value is not None and value != "" and value != []:
                return value
        return None

    def _pick_list_field(
        self, source_map: dict[str, MovieData], priority: list[str], field: str
    ) -> list:
        """Pick a list field, preferring the first non-empty list."""
        for source_name in priority:
            if source_name in source_map:
                value = getattr(source_map[source_name], field, [])
                if value:
                    return value
        for data in source_map.values():
            value = getattr(data, field, [])
            if value:
                return value
        return []

    def _post_process(self, data: MovieData) -> None:
        """Apply post-processing: genre replacement, display name, etc."""
        # Clean title
        if data.title:
            data.title = clean_title(data.title)
        if data.alternate_title:
            data.alternate_title = clean_title(data.alternate_title)

        # Build display name
        nfo_config = self.config.sort.metadata.nfo
        data.display_name = format_template(
            nfo_config.display_name,
            {
                "id": data.id,
                "title": data.title or "",
                "studio": data.maker or "",
                "year": str(data.release_year) if data.release_year else "",
            },
        )

        # Apply genre replacements from CSV
        if self.config.sort.metadata.genre_csv.enabled:
            data.genres = self._replace_genres(data.genres)

        # Filter ignored genre patterns
        data.genres = self._filter_genres(data.genres)

        # Resolve actress thumbnails from cache
        if self.config.sort.metadata.thumb_csv.enabled:
            self._resolve_actress_thumbs(data)

        # Tags from config format
        for tag_fmt in nfo_config.format_tag:
            tag_value = format_template(
                tag_fmt,
                {
                    "id": data.id,
                    "set": data.series or "",
                    "studio": data.maker or "",
                    "label": data.label or "",
                },
            )
            if tag_value and tag_value not in data.tags:
                data.tags.append(tag_value)

        # Tagline
        if nfo_config.format_tagline:
            data.tagline = format_template(
                nfo_config.format_tagline,
                {
                    "id": data.id,
                    "title": data.title or "",
                    "studio": data.maker or "",
                },
            )

    def _replace_genres(self, genres: list[str]) -> list[str]:
        """Replace genres using the genre CSV mapping."""
        if self._genre_map is None:
            self._load_genre_csv()

        if not self._genre_map:
            return genres

        result = []
        for genre in genres:
            replacement = self._genre_map.get(genre.lower())
            if replacement is not None:
                if replacement:  # Non-empty = replacement
                    result.append(replacement)
                # Empty string = remove genre
            else:
                result.append(genre)
        return result

    def _filter_genres(self, genres: list[str]) -> list[str]:
        """Remove genres matching ignored patterns."""
        if self._genre_ignore is None:
            patterns_raw = self.config.sort.metadata.genre_csv.ignored_patterns
            self._genre_ignore = [re.compile(p, re.IGNORECASE) for p in patterns_raw]

        return [g for g in genres if not any(p.search(g) for p in self._genre_ignore)]

    def _resolve_actress_thumbs(self, data: MovieData) -> None:
        """Resolve actress thumbnails from the thumbs CSV cache."""
        if self._thumb_cache is None:
            self._load_thumb_csv()

        if not self._thumb_cache:
            return

        for actress in data.actresses:
            if actress.thumb_url:
                continue
            # Try matching by name
            key = actress.full_name.lower()
            if key in self._thumb_cache:
                actress.thumb_url = self._thumb_cache[key]
            elif actress.japanese_name and actress.japanese_name.lower() in self._thumb_cache:
                actress.thumb_url = self._thumb_cache[actress.japanese_name.lower()]

    def _load_genre_csv(self) -> None:
        """Load genre replacement CSV into memory."""
        self._genre_map = {}
        csv_path = self._resolve_data_path("genres.csv")
        if not csv_path or not csv_path.exists():
            return

        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    original = row.get("Original", "").strip().lower()
                    replacement = row.get("Replacement", "").strip()
                    if original:
                        self._genre_map[original] = replacement
        except Exception as exc:
            logger.error("genre_csv_load_error", error=str(exc))

    def _load_thumb_csv(self) -> None:
        """Load actress thumbnail CSV into memory."""
        self._thumb_cache = {}
        csv_path = self._resolve_data_path("thumbs.csv")
        if not csv_path or not csv_path.exists():
            return

        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = (row.get("FullName", "") or row.get("Name", "")).strip().lower()
                    thumb = row.get("ThumbUrl", "").strip()
                    if name and thumb:
                        self._thumb_cache[name] = thumb
        except Exception as exc:
            logger.error("thumb_csv_load_error", error=str(exc))

    def _resolve_data_path(self, filename: str) -> Path | None:
        """Resolve a data file path from config or default location."""
        # Check config override
        locations = self.config.locations
        overrides = {
            "genres.csv": locations.genre_csv,
            "thumbs.csv": locations.thumb_csv,
            "tags.csv": locations.tag_csv,
        }
        override = overrides.get(filename, "")
        if override:
            return Path(override)

        # Default: look in package data directory
        data_dir = Path(__file__).parent.parent / "data"
        candidate = data_dir / filename
        if candidate.exists():
            return candidate

        return None
