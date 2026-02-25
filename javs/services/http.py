"""Async HTTP client with retry, proxy, and rate limiting support."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from javs.utils.logging import get_logger

logger = get_logger(__name__)


# Default headers to mimic a browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
}

# Age verification cookies for DMM
DMM_COOKIES = {
    "age_check_done": "1",
    "ckcy": "2",
    "cklg": "en",
}


class CloudflareBlockedError(Exception):
    """Raised when Cloudflare blocks all bypass attempts."""


class HttpClient:
    """Async HTTP client with built-in retry, proxy, and cookie support.

    Replaces Javinizer's Invoke-WebRequest and custom ExtendedWebClient C# class.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        proxy_auth: tuple[str, str] | None = None,
        timeout_seconds: int = 30,
        max_concurrent: int = 10,
        cf_clearance: str | None = None,
        cf_user_agent: str | None = None,
    ):
        self.proxy_url = proxy_url
        self.proxy_auth = aiohttp.BasicAuth(*proxy_auth) if proxy_auth else None
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: aiohttp.ClientSession | None = None
        self.cf_clearance = cf_clearance or ""
        self.cf_user_agent = cf_user_agent or ""

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazily create and return the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=DEFAULT_HEADERS,
            )
        return self._session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> str:
        """HTTP GET request with retry.

        Args:
            url: Target URL.
            headers: Extra headers to merge with defaults.
            cookies: Cookies to send.
            params: Query parameters.
            allow_redirects: Follow redirects.

        Returns:
            Response body as string.
        """
        async with self._semaphore:
            session = await self._get_session()
            merged_headers = {**DEFAULT_HEADERS, **(headers or {})}

            logger.debug("http_get", url=url)
            async with session.get(
                url,
                headers=merged_headers,
                cookies=cookies,
                params=params,
                proxy=self.proxy_url,
                proxy_auth=self.proxy_auth,
                allow_redirects=allow_redirects,
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                return await resp.text()

    async def get_cf(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> str:
        """HTTP GET with Cloudflare bypass.

        Strategy (layered):
          1. If cf_clearance cookie is configured → use it with aiohttp (fastest)
          2. Otherwise → try cloudscraper (handles basic CF challenges)
          3. If both fail → raise with clear user instructions

        Args:
            url: Target URL behind Cloudflare.
            headers: Extra headers.
            cookies: Extra cookies.
            params: Query parameters.
            allow_redirects: Follow redirects.

        Returns:
            Response body as string.

        Raises:
            CloudflareBlockedError: When all bypass methods fail.
        """
        # Layer 1: Manual cookies (fastest, most reliable)
        if self.cf_clearance:
            logger.debug("http_get_cf_manual", url=url)
            ua = self.cf_user_agent or DEFAULT_HEADERS["User-Agent"]
            manual_cookies = {**(cookies or {}), "cf_clearance": self.cf_clearance}
            manual_headers = {**(headers or {}), "User-Agent": ua}
            try:
                return await self.get(
                    url,
                    headers=manual_headers,
                    cookies=manual_cookies,
                    params=params,
                    allow_redirects=allow_redirects,
                )
            except Exception as exc:
                logger.warning(
                    "cf_manual_failed",
                    url=url,
                    error=str(exc),
                    hint="cf_clearance cookie may be expired, refresh it in config",
                )

        # Layer 2: cloudscraper (handles basic CF JS challenges)
        import cloudscraper

        def _sync_get() -> str:
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            merged = {**DEFAULT_HEADERS, **(headers or {})}
            resp = scraper.get(
                url,
                headers=merged,
                cookies=cookies,
                params=params,
                allow_redirects=allow_redirects,
                timeout=self.timeout.total or 30,
            )
            resp.raise_for_status()
            return resp.text

        try:
            async with self._semaphore:
                logger.debug("http_get_cf_auto", url=url)
                return await asyncio.to_thread(_sync_get)
        except Exception as exc:
            raise CloudflareBlockedError(
                f"Cloudflare blocked access to {url}. "
                f"All bypass methods failed.\n\n"
                f"To fix this:\n"
                f"  1. Open {url} in your browser\n"
                f"  2. Solve the Cloudflare challenge\n"
                f"  3. Open DevTools (F12) → Application → Cookies\n"
                f"  4. Copy the 'cf_clearance' cookie value\n"
                f"  5. Copy your User-Agent from DevTools → Network tab\n"
                f"  6. Paste both into your config.yaml under 'cloudflare:'\n"
                f"\n"
                f"Original error: {exc}"
            ) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        """HTTP GET and parse response as JSON."""
        async with self._semaphore:
            session = await self._get_session()
            merged_headers = {**DEFAULT_HEADERS, **(headers or {})}

            logger.debug("http_get_json", url=url)
            async with session.get(
                url,
                headers=merged_headers,
                cookies=cookies,
                params=params,
                proxy=self.proxy_url,
                proxy_auth=self.proxy_auth,
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                return await resp.json(content_type=None)

    async def download(
        self,
        url: str,
        dest: Path,
        cookies: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> bool:
        """Download a file to disk.

        Args:
            url: URL of the file.
            dest: Destination path.
            cookies: Optional cookies.
            timeout: Override timeout for large files.

        Returns:
            True if download succeeded.
        """
        try:
            async with self._semaphore:
                session = await self._get_session()
                req_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else self.timeout

                logger.debug("http_download", url=url, dest=str(dest))
                async with session.get(
                    url,
                    cookies=cookies,
                    proxy=self.proxy_url,
                    proxy_auth=self.proxy_auth,
                    timeout=req_timeout,
                    ssl=False,
                ) as resp:
                    resp.raise_for_status()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with open(dest, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            f.write(chunk)
            return True
        except Exception as exc:
            logger.error("http_download_failed", url=url, error=str(exc))
            return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
