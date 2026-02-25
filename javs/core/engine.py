"""Main orchestrator engine for javs.

Coordinates scraping, aggregation, and file organization.
Replaces the process block of Javinizer.ps1.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from javs.config import JavsConfig, load_config
from javs.core.aggregator import DataAggregator
from javs.core.organizer import FileOrganizer
from javs.core.scanner import FileScanner
from javs.models.file import ScannedFile
from javs.models.movie import MovieData
from javs.scrapers.registry import ScraperRegistry
from javs.services.http import HttpClient
from javs.services.translator import translate_movie_data
from javs.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


class JavsEngine:
    """Main engine that orchestrates the entire javs workflow.

    Pipeline:
    1. Scan files → extract movie IDs
    2. Scrape metadata from enabled sources (async)
    3. Aggregate data by priority
    4. Translate if configured
    5. Sort/rename/organize files
    """

    def __init__(self, config: JavsConfig | None = None) -> None:
        self.config = config or load_config()
        setup_logging(
            level=self.config.log.level,
            log_file=self.config.locations.log or None,
        )

        # Initialize components
        proxy_url = self.config.proxy.host if self.config.proxy.enabled else None
        proxy_auth = None
        if self.config.proxy.enabled and self.config.proxy.username:
            proxy_auth = (self.config.proxy.username, self.config.proxy.password)

        self.http = HttpClient(
            proxy_url=proxy_url,
            proxy_auth=proxy_auth,
            timeout_seconds=self.config.sort.download.timeout_seconds,
            max_concurrent=self.config.throttle_limit * 3,
        )
        self.scanner = FileScanner(self.config.match)
        self.aggregator = DataAggregator(self.config)
        self.organizer = FileOrganizer(self.config, self.http)

        # Load all scrapers
        ScraperRegistry.load_all()

    async def find(
        self,
        movie_id: str,
        scraper_names: list[str] | None = None,
        aggregate: bool = True,
    ) -> MovieData | None:
        """Look up metadata for a single movie ID.

        Args:
            movie_id: JAV movie ID (e.g., "ABP-420").
            scraper_names: Override which scrapers to use.
            aggregate: Whether to aggregate results.

        Returns:
            MovieData or None.
        """
        async with self.http:
            if scraper_names:
                scrapers = ScraperRegistry.get_by_names(scraper_names, self.http)
            else:
                scrapers = ScraperRegistry.get_enabled(self.config.scrapers, self.http)

            if not scrapers:
                logger.error("no_scrapers_enabled")
                return None

            logger.info("finding", movie_id=movie_id, scrapers=[s.name for s in scrapers])

            # Run all scrapers concurrently
            tasks = [s.search_and_scrape(movie_id) for s in scrapers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter valid results
            valid = [r for r in results if isinstance(r, MovieData)]
            errors = [r for r in results if isinstance(r, Exception)]

            for err in errors:
                logger.warning("scraper_exception", error=str(err))

            if not valid:
                logger.warning("no_results", movie_id=movie_id)
                return None

            logger.info("results_found", count=len(valid), sources=[v.source for v in valid])

            if not aggregate:
                return valid[0]

            # Aggregate
            merged = self.aggregator.merge(valid)

            # Translate if configured
            translate_config = self.config.sort.metadata.nfo.translate
            if translate_config.enabled:
                merged = await translate_movie_data(merged, translate_config)

            return merged

    async def sort_path(
        self,
        source: Path,
        dest: Path,
        recurse: bool = False,
        force: bool = False,
        preview: bool = False,
    ) -> list[MovieData]:
        """Scan a directory and sort all matching files.

        Args:
            source: Source directory or file.
            dest: Destination root directory.
            recurse: Scan subdirectories.
            force: Overwrite existing files.
            preview: Dry run mode.

        Returns:
            List of successfully processed MovieData.
        """
        # 1. Scan files
        files = self.scanner.scan(source, recurse=recurse)
        if not files:
            logger.warning("no_files_found", path=str(source))
            return []

        logger.info("files_scanned", count=len(files))

        # 2. Process each file
        results: list[MovieData] = []
        sem = asyncio.Semaphore(self.config.throttle_limit)

        async def process_one(file: ScannedFile) -> MovieData | None:
            async with sem:
                data = await self.find(file.movie_id)
                if not data:
                    logger.warning("skip_no_data", file=file.filename, id=file.movie_id)
                    return None

                # Apply original filename tracking
                data.original_filename = file.filename

                # Sort
                await self.organizer.sort_movie(file, data, dest, force=force, preview=preview)

                # Sleep between files to avoid rate limiting
                if self.config.sleep > 0:
                    await asyncio.sleep(self.config.sleep)

                return data

        async with self.http:
            tasks = [process_one(f) for f in files]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in task_results:
            if isinstance(r, MovieData):
                results.append(r)
            elif isinstance(r, Exception):
                logger.error("process_error", error=str(r))

        logger.info("sort_complete", processed=len(results), total=len(files))
        return results

    async def close(self) -> None:
        """Clean up resources."""
        await self.http.close()
