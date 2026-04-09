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
from javs.core.runtime import EngineRuntime, build_runtime
from javs.core.scanner import FileScanner
from javs.models.file import ScannedFile
from javs.models.movie import MovieData
from javs.scrapers.registry import ScraperRegistry
from javs.services.http import (
    CloudflareBlockedError,
    HttpClient,
    InvalidProxyAuthError,
    ProxyConnectionFailedError,
)
from javs.services.javlibrary_auth import JavlibraryCredentials
from javs.services.translator import get_translation_provider_issue, translate_movie_data
from javs.utils.logging import get_logger, get_mask_processor, setup_logging

logger = get_logger(__name__)


def _empty_run_summary() -> dict[str, int]:
    """Return zeroed counters for the latest public engine run."""
    return {
        "total": 0,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "warnings": 0,
    }


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
        runtime: EngineRuntime | None = None,
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
        self.last_run_diagnostics: list[dict[str, str]] = []
        self.last_run_summary: dict[str, int] = _empty_run_summary()
        self.last_preview_plan: list[dict[str, str]] = []

        self.runtime = runtime or build_runtime(
            self.config,
            http_cls=HttpClient,
            scanner_cls=FileScanner,
            aggregator_cls=DataAggregator,
            organizer_cls=FileOrganizer,
            mask_processor=get_mask_processor(),
        )
        self.http = self.runtime.http
        self.scanner = self.runtime.scanner
        self.aggregator = self.runtime.aggregator
        self.organizer = self.runtime.organizer

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
        data = await self._find_merged(movie_id, scraper_names=scraper_names, aggregate=aggregate)
        if not data:
            return None

        return await self._translate_for_display(data)

    async def _find_merged(
        self,
        movie_id: str,
        scraper_names: list[str] | None = None,
        aggregate: bool = True,
    ) -> MovieData | None:
        """Look up and aggregate raw movie metadata without translation side effects."""
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

        valid: list[MovieData] = []
        for scraper, result in zip(scrapers, results, strict=False):
            if isinstance(result, MovieData):
                valid.append(result)
                continue
            if isinstance(result, Exception):
                self._record_run_diagnostic(scraper.name, result)
                if isinstance(result, CloudflareBlockedError):
                    logger.warning(
                        "scraper_cloudflare_blocked",
                        scraper=scraper.name,
                        error=str(result),
                    )
                else:
                    logger.warning(
                        "scraper_exception",
                        scraper=scraper.name,
                        error=str(result),
                    )

        if not valid:
            logger.warning("no_results", movie_id=movie_id)
            return None

        logger.info("results_found", count=len(valid), sources=[v.source for v in valid])

        if not aggregate:
            return valid[0]

        return self.aggregator.merge(valid)

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
        self._reset_run_diagnostics()
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
        cleanup_empty_source_dir: bool | None = None,
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
        self._reset_run_diagnostics()
        effective_cleanup_empty_source_dir = (
            self.config.sort.cleanup_empty_source_dir
            if cleanup_empty_source_dir is None
            else cleanup_empty_source_dir
        )
        files = self.scanner.scan(source, recurse=recurse)
        if not files:
            logger.warning("no_files_found", path=str(source))
            return []

        logger.info("files_scanned", count=len(files))

        async def sort_one(file: ScannedFile, data: MovieData, nfo_data: MovieData | None) -> None:
            paths = await self.organizer.sort_movie(
                file,
                data,
                dest,
                force=force,
                preview=preview,
                nfo_data=nfo_data,
                cleanup_empty_source_dir=effective_cleanup_empty_source_dir,
            )
            if preview:
                self.last_preview_plan.append(
                    {
                        "source": str(file.path),
                        "id": data.id,
                        "target": str(paths.file_path),
                    }
                )

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
        self._reset_run_diagnostics()
        files = self.scanner.scan(source, recurse=recurse)
        if not files:
            logger.warning("no_files_found", path=str(source))
            return []

        logger.info("files_scanned", count=len(files), mode="update")

        async def update_one(
            file: ScannedFile,
            data: MovieData,
            nfo_data: MovieData | None,
        ) -> None:
            paths = await self.organizer.update_movie(
                file,
                data,
                force=force,
                preview=preview,
                refresh_images=refresh_images,
                refresh_trailer=refresh_trailer,
                nfo_data=nfo_data,
            )
            if preview:
                self.last_preview_plan.append(
                    {
                        "source": str(file.path),
                        "id": data.id,
                        "target": str(paths.nfo_path),
                    }
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

    def get_last_run_diagnostics(self) -> list[dict[str, str]]:
        """Return a copy of diagnostics from the last engine run."""
        return [dict(item) for item in self.last_run_diagnostics]

    async def _run_scrapers(self, scrapers, movie_id: str) -> list[MovieData | Exception | None]:
        """Run scraper tasks concurrently and keep exception objects for inspection."""
        tasks = [s.search_and_scrape(movie_id) for s in scrapers]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_scanned_files(
        self,
        files: list[ScannedFile],
        *,
        process_movie: Callable[[ScannedFile, MovieData, MovieData | None], Awaitable[None]],
        scraper_names: list[str] | None = None,
    ) -> list[MovieData]:
        """Process a batch of scanned files with shared scrape pacing and session lifecycle."""
        results: list[MovieData] = []
        skipped = 0
        failed = 0
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
                raw_data = await self._find_merged(file.movie_id, scraper_names=scraper_names)
            finally:
                schedule_scrape_slot_release(
                    apply_sleep=not is_last and waiting_for_scrape_slot > 0
                )

            if not raw_data:
                logger.warning("skip_no_data", file=file.filename, id=file.movie_id)
                return None

            translated_data = await self._translate_for_display(raw_data)
            active_data = (
                translated_data
                if self.config.sort.metadata.nfo.translate.affect_sort_names
                else raw_data
            )

            missing_fields = self._missing_required_fields(active_data)
            if missing_fields:
                logger.warning(
                    "skip_missing_required_fields",
                    file=file.filename,
                    id=file.movie_id,
                    missing_fields=missing_fields,
                )
                return None

            active_data.original_filename = file.filename
            translated_data.original_filename = file.filename
            await process_movie(file, active_data, translated_data)
            return active_data

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
                failed += 1
                logger.error("process_error", error=str(result))
            else:
                skipped += 1

        self.last_run_summary = {
            "total": total_files,
            "processed": len(results),
            "skipped": skipped,
            "failed": failed,
            "warnings": len(self.last_run_diagnostics),
        }

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

        original_auth = (
            getattr(self.http, "cf_clearance", ""),
            getattr(self.http, "cf_user_agent", ""),
        )
        should_retry = False

        async with self._cloudflare_recovery_lock:
            if (
                getattr(self.http, "cf_clearance", ""),
                getattr(self.http, "cf_user_agent", ""),
            ) != original_auth:
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

    async def _translate_for_display(self, data: MovieData) -> MovieData:
        """Return translated movie data when translation is enabled, otherwise the original data."""
        translate_config = self.config.sort.metadata.nfo.translate
        if not translate_config.enabled:
            return data

        issue = get_translation_provider_issue(translate_config)
        if issue is not None:
            self._record_diagnostic_item(
                kind=issue.kind,
                scraper="translate",
                detail=issue.detail,
            )
            return data

        return await translate_movie_data(data.model_copy(deep=True), translate_config)

    def _reset_cloudflare_recovery_state(self) -> None:
        """Reset once-per-run Javlibrary Cloudflare recovery guard."""
        self._cloudflare_recovery_used = False

    def _reset_run_diagnostics(self) -> None:
        """Clear user-facing run diagnostics before a new public operation."""
        self.last_run_diagnostics = []
        self.last_run_summary = _empty_run_summary()
        self.last_preview_plan = []

    def _record_run_diagnostic(self, scraper: str, error: Exception) -> None:
        """Record compact scraper diagnostics for CLI summaries."""
        kind = self._diagnostic_kind_for_error(error)
        if kind is None:
            return

        self._record_diagnostic_item(kind=kind, scraper=scraper)

    def _record_diagnostic_item(
        self,
        *,
        kind: str,
        scraper: str,
        detail: str | None = None,
    ) -> None:
        """Record a compact diagnostic item once per public run."""
        diagnostic = {"kind": kind, "scraper": scraper}
        if detail:
            diagnostic["detail"] = detail
        if diagnostic not in self.last_run_diagnostics:
            self.last_run_diagnostics.append(diagnostic)

    def _diagnostic_kind_for_error(self, error: Exception) -> str | None:
        """Map runtime exceptions to compact diagnostic kinds."""
        if isinstance(error, InvalidProxyAuthError):
            return "proxy_auth_failed"
        if isinstance(error, ProxyConnectionFailedError):
            return "proxy_unreachable"
        if isinstance(error, CloudflareBlockedError):
            return "cloudflare_blocked"
        return None

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
