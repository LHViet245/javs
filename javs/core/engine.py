"""Main orchestrator engine for javs.

Coordinates scraping, aggregation, and file organization.
Replaces the process block of Javinizer.ps1.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from javs.config import JavsConfig, load_config
from javs.core.aggregator import DataAggregator
from javs.core.organizer import FileOrganizer
from javs.core.scanner import FileScanner
from javs.models.file import ScannedFile
from javs.models.movie import MovieData
from javs.scrapers.registry import ScraperRegistry
from javs.services.http import CloudflareBlockedError, HttpClient
from javs.services.javlibrary_auth import JavlibraryCredentials
from javs.services.translator import translate_movie_data
from javs.utils.logging import get_logger, get_mask_processor, setup_logging

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

    _EMPTY_REQUIRED_VALUES: tuple[object, ...] = (None, "", [], {})

    def __init__(
        self,
        config: JavsConfig | None = None,
        cloudflare_recovery_handler: (
            Callable[[CloudflareBlockedError], Awaitable[JavlibraryCredentials | None]]
            | None
        ) = None,
    ) -> None:
        self.config = config or load_config()
        setup_logging(
            level=self.config.log.level,
            log_file=self.config.locations.log or None,
        )
        self._cloudflare_recovery_handler = cloudflare_recovery_handler
        self._cloudflare_recovery_lock = asyncio.Lock()
        self._cloudflare_recovery_used = False

        # Initialize components
        proxy_url = self.config.proxy.url if self.config.proxy.enabled else None

        # Register proxy URL with credential masking
        if proxy_url:
            mask_proc = get_mask_processor()
            mask_proc.set_proxy_url(proxy_url, self.config.proxy.masked_url)

        self.http = HttpClient(
            proxy_url=proxy_url,
            timeout_seconds=self.config.sort.download.timeout_seconds,
            max_concurrent=self.config.throttle_limit * 3,
            max_retries=self.config.proxy.max_retries if self.config.proxy.enabled else 3,
            cf_clearance=self.config.javlibrary.cookie_cf_clearance,
            cf_user_agent=self.config.javlibrary.browser_user_agent,
            verify_ssl=False,  # Most scraping sites have SSL issues; explicit trade-off
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

        Assumes the HTTP session is already open (managed by caller).
        For standalone CLI usage, use ``find_one()`` instead.

        Args:
            movie_id: JAV movie ID (e.g., "ABP-420").
            scraper_names: Override which scrapers to use.
            aggregate: Whether to aggregate results.

        Returns:
            MovieData or None.
        """
        if scraper_names:
            scrapers = ScraperRegistry.get_by_names(
                scraper_names, self.http, self.config.scrapers, self.config.proxy
            )
        else:
            scrapers = ScraperRegistry.get_enabled(
                self.config.scrapers,
                self.http,
                self.config.proxy,
            )

        if not scrapers:
            logger.error("no_scrapers_enabled")
            return None

        logger.info("finding", movie_id=movie_id, scrapers=[s.name for s in scrapers])

        results = await self._run_scrapers(scrapers, movie_id)

        cloudflare_failures = [
            (scraper, result)
            for scraper, result in zip(scrapers, results, strict=False)
            if isinstance(result, CloudflareBlockedError) and scraper.name.startswith("javlibrary")
        ]
        if cloudflare_failures:
            retry_scrapers = [scraper for scraper, _result in cloudflare_failures]
            recovered_results = await self._recover_javlibrary_and_retry(
                movie_id=movie_id,
                scrapers=retry_scrapers,
                error=cloudflare_failures[0][1],
            )
            for scraper, recovered in zip(retry_scrapers, recovered_results, strict=False):
                idx = scrapers.index(scraper)
                results[idx] = recovered

        # Filter valid results
        valid = [r for r in results if isinstance(r, MovieData)]
        errors = [r for r in results if isinstance(r, Exception)]

        for err in errors:
            if isinstance(err, CloudflareBlockedError):
                logger.warning("scraper_cloudflare_blocked", error=str(err))
            else:
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

    async def find_one(
        self,
        movie_id: str,
        scraper_names: list[str] | None = None,
        aggregate: bool = True,
    ) -> MovieData | None:
        """Public entrypoint: look up a single movie with managed session lifecycle.

        Unlike ``find()``, this opens and closes the HTTP session automatically.
        Use this from CLI commands or other standalone callers.
        """
        self._reset_cloudflare_recovery_state()
        async with self.http:
            return await self.find(movie_id, scraper_names, aggregate)

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
        files = self.scanner.scan(source, recurse=recurse)
        if not files:
            logger.warning("no_files_found", path=str(source))
            return []

        logger.info("files_scanned", count=len(files))

        async def sort_one(file: ScannedFile, data: MovieData) -> None:
            await self.organizer.sort_movie(file, data, dest, force=force, preview=preview)

        results = await self._process_scanned_files(files, process_movie=sort_one)
        logger.info("sort_complete", processed=len(results), total=len(files))
        return results

    async def update_path(
        self,
        source: Path,
        recurse: bool = False,
        force: bool = False,
        preview: bool = False,
        scraper_names: list[str] | None = None,
        refresh_images: bool = False,
        refresh_trailer: bool = False,
    ) -> list[MovieData]:
        """Refresh metadata sidecars for an already-sorted library without moving videos."""
        files = self.scanner.scan(source, recurse=recurse)
        if not files:
            logger.warning("no_files_found", path=str(source))
            return []

        logger.info("files_scanned", count=len(files), mode="update")

        async def update_one(file: ScannedFile, data: MovieData) -> None:
            await self.organizer.update_movie(
                file,
                data,
                force=force,
                preview=preview,
                refresh_images=refresh_images,
                refresh_trailer=refresh_trailer,
            )

        results = await self._process_scanned_files(
            files,
            scraper_names=scraper_names,
            process_movie=update_one,
        )
        logger.info("update_complete", processed=len(results), total=len(files))
        return results

    async def close(self) -> None:
        """Clean up resources."""
        await self.http.close()

    async def _run_scrapers(self, scrapers, movie_id: str) -> list[MovieData | Exception | None]:
        """Run scraper tasks concurrently and keep exception objects for inspection."""
        tasks = [s.search_and_scrape(movie_id) for s in scrapers]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_scanned_files(
        self,
        files: list[ScannedFile],
        *,
        process_movie: Callable[[ScannedFile, MovieData], Awaitable[None]],
        scraper_names: list[str] | None = None,
    ) -> list[MovieData]:
        """Process a batch of scanned files with shared scrape pacing and session lifecycle."""
        results: list[MovieData] = []
        scrape_sem = asyncio.Semaphore(self.config.throttle_limit)
        cooldown_tasks: set[asyncio.Task[None]] = set()
        waiting_for_scrape_slot = 0
        total_files = len(files)

        def schedule_scrape_slot_release(*, apply_sleep: bool) -> None:
            async def release_later() -> None:
                try:
                    if apply_sleep and self.config.sleep > 0:
                        await asyncio.sleep(self.config.sleep)
                finally:
                    scrape_sem.release()

            task = asyncio.create_task(release_later())
            cooldown_tasks.add(task)
            task.add_done_callback(cooldown_tasks.discard)

        async def process_one(file: ScannedFile, *, is_last: bool) -> MovieData | None:
            nonlocal waiting_for_scrape_slot
            waiting_for_scrape_slot += 1
            await scrape_sem.acquire()
            waiting_for_scrape_slot -= 1
            try:
                data = await self.find(file.movie_id, scraper_names=scraper_names)
            finally:
                schedule_scrape_slot_release(
                    apply_sleep=not is_last and waiting_for_scrape_slot > 0
                )

            if not data:
                logger.warning("skip_no_data", file=file.filename, id=file.movie_id)
                return None

            missing_fields = self._missing_required_fields(data)
            if missing_fields:
                logger.warning(
                    "skip_missing_required_fields",
                    file=file.filename,
                    id=file.movie_id,
                    missing_fields=missing_fields,
                )
                return None

            data.original_filename = file.filename
            await process_movie(file, data)
            return data

        async with self.http:
            self._reset_cloudflare_recovery_state()
            tasks = [process_one(f, is_last=idx == total_files - 1) for idx, f in enumerate(files)]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            if cooldown_tasks:
                await asyncio.gather(*cooldown_tasks, return_exceptions=True)

        for result in task_results:
            if isinstance(result, MovieData):
                results.append(result)
            elif isinstance(result, Exception):
                logger.error("process_error", error=str(result))

        return results

    async def _recover_javlibrary_and_retry(
        self,
        movie_id: str,
        scrapers,
        error: CloudflareBlockedError,
    ) -> list[MovieData | Exception | None]:
        """Refresh Javlibrary credentials once per run, then retry only affected scrapers."""
        if not scrapers:
            return []

        original_auth = (self.http.cf_clearance, self.http.cf_user_agent)
        should_retry = False

        async with self._cloudflare_recovery_lock:
            if (self.http.cf_clearance, self.http.cf_user_agent) != original_auth:
                should_retry = True
            elif (
                self._cloudflare_recovery_handler is not None
                and not self._cloudflare_recovery_used
            ):
                self._cloudflare_recovery_used = True
                credentials = await self._cloudflare_recovery_handler(error)
                if credentials is not None:
                    self.update_javlibrary_credentials(credentials)
                    should_retry = True

        if not should_retry:
            return []

        return await self._run_scrapers(scrapers, movie_id)

    def update_javlibrary_credentials(self, credentials: JavlibraryCredentials) -> None:
        """Apply refreshed Javlibrary credentials to config and shared HTTP runtime."""
        self.config.javlibrary.cookie_cf_clearance = credentials.cf_clearance
        self.config.javlibrary.browser_user_agent = credentials.browser_user_agent
        self.http.update_cf_credentials(
            cf_clearance=credentials.cf_clearance,
            cf_user_agent=credentials.browser_user_agent,
        )

    def _reset_cloudflare_recovery_state(self) -> None:
        """Reset once-per-run Javlibrary Cloudflare recovery guard."""
        self._cloudflare_recovery_used = False

    def _missing_required_fields(self, data: MovieData) -> list[str]:
        """Return configured required fields missing from aggregated movie data."""
        missing: list[str] = []
        required_fields = self.config.sort.metadata.required_fields

        for field_name in required_fields:
            if not hasattr(data, field_name):
                missing.append(field_name)
                continue

            value = getattr(data, field_name)
            if value in self._EMPTY_REQUIRED_VALUES:
                missing.append(field_name)

        return missing
