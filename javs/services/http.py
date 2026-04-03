"""Async HTTP client with retry, proxy (HTTP/HTTPS/SOCKS5), and rate limiting support."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import aiofiles
import aiohttp
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from yarl import URL

from javs.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


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


# --- Custom Exceptions ---


class CloudflareBlockedError(Exception):
    """Raised when Cloudflare blocks all bypass attempts."""

    def __init__(self, message: str, *, guidance: str | None = None) -> None:
        super().__init__(message)
        self.guidance = guidance or ""


class InvalidProxyAuthError(Exception):
    """Raised on HTTP 407 — proxy auth failed. Do NOT retry."""


class ProxyConnectionFailedError(Exception):
    """Raised when proxy server is unreachable."""


# --- Retry exception types (will include proxy errors dynamically) ---

_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    ProxyConnectionFailedError,
)

# Try to extend with aiohttp-socks exceptions if available
try:
    from aiohttp_socks import ProxyConnectionError as SocksProxyConnectionError

    _RETRY_EXCEPTIONS = (*_RETRY_EXCEPTIONS, SocksProxyConnectionError)
except ImportError:
    pass


class HttpClient:
    """Async HTTP client with built-in retry, proxy, and cookie support.

    Supports HTTP/HTTPS/SOCKS5 proxies with connection pooling.
    Replaces Javinizer's Invoke-WebRequest and custom ExtendedWebClient C# class.
    """

    def __init__(
        self,
        proxy_url: str | None = None,
        timeout_seconds: int = 30,
        max_concurrent: int = 10,
        cf_clearance: str | None = None,
        cf_user_agent: str | None = None,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ):
        self._proxy_url = proxy_url
        self._proxy_masked: str | None = None
        self._is_socks = False

        # Parse proxy URL if provided
        if proxy_url:
            self._is_socks = proxy_url.startswith(("socks4", "socks5"))
            try:
                parsed = URL(proxy_url)
                if parsed.password:
                    self._proxy_masked = str(parsed.with_password("***").with_user("***"))
                else:
                    self._proxy_masked = proxy_url
            except Exception:
                self._proxy_masked = proxy_url

        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session_direct: aiohttp.ClientSession | None = None
        self._session_proxy: aiohttp.ClientSession | None = None
        self._max_retries = max_retries
        self._verify_ssl = verify_ssl
        self.cf_clearance = cf_clearance or ""
        self.cf_user_agent = cf_user_agent or ""

        if proxy_url:
            logger.info("proxy_configured", proxy=self._proxy_masked, socks=self._is_socks)

    def update_cf_credentials(self, *, cf_clearance: str, cf_user_agent: str) -> None:
        """Update Cloudflare credentials for subsequent requests."""
        self.cf_clearance = cf_clearance
        self.cf_user_agent = cf_user_agent

    def _create_connector(self) -> aiohttp.BaseConnector:
        """Create the appropriate connector based on proxy type.

        SOCKS proxies need ProxyConnector from aiohttp-socks.
        HTTP/HTTPS proxies use standard TCPConnector (proxy passed per-request).
        """
        if self._proxy_url and self._is_socks:
            from aiohttp_socks import ProxyConnector

            return ProxyConnector.from_url(
                self._proxy_url,
                limit=100,
                enable_cleanup_closed=True,
            )
        return aiohttp.TCPConnector(
            limit=100,
            enable_cleanup_closed=True,
        )

    async def _get_session(self, use_proxy: bool = False) -> aiohttp.ClientSession:
        """Lazily create and return the appropriate aiohttp session.

        Uses dual sessions to ensure SOCKS proxy routing is per-scraper:
        - use_proxy=True  → session with ProxyConnector (SOCKS) or per-request proxy (HTTP)
        - use_proxy=False → plain TCPConnector, never routes through proxy
        """
        if use_proxy and self._proxy_url:
            if self._session_proxy is None or self._session_proxy.closed:
                connector = self._create_connector()
                self._session_proxy = aiohttp.ClientSession(
                    connector=connector,
                    timeout=self.timeout,
                    headers=DEFAULT_HEADERS,
                )
            return self._session_proxy

        if self._session_direct is None or self._session_direct.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                enable_cleanup_closed=True,
            )
            self._session_direct = aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers=DEFAULT_HEADERS,
            )
        return self._session_direct

    def _get_proxy_kwargs(self, use_proxy: bool) -> dict[str, Any]:
        """Build proxy kwargs for aiohttp session.get().

        For SOCKS proxies, the connector handles routing — no per-request kwargs.
        For HTTP/HTTPS proxies, pass proxy URL per-request.
        """
        if not use_proxy or not self._proxy_url:
            return {}
        if self._is_socks:
            # SOCKS proxy is handled at connector level, no per-request param
            return {}
        # HTTP/HTTPS proxy: pass per-request
        return {"proxy": self._proxy_url}

    def _check_proxy_status(self, resp: aiohttp.ClientResponse) -> None:
        """Check for proxy-specific HTTP errors before generic raise_for_status.

        Raises:
            InvalidProxyAuthError: On 407 (wrong proxy credentials).
        """
        if resp.status == 407:
            raise InvalidProxyAuthError(
                f"Proxy authentication failed (HTTP 407). "
                f"Check proxy credentials in config. "
                f"Proxy: {self._proxy_masked or 'unknown'}"
            )

    def _sanitize_error(self, exc: Exception) -> str:
        """Remove raw proxy credentials from exception messages."""
        msg = str(exc)
        if self._proxy_url and self._proxy_masked:
            msg = msg.replace(self._proxy_url, self._proxy_masked)
        return msg

    def _retrying(self) -> AsyncRetrying:
        """Build the retry policy using the configured retry count."""
        return AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
            reraise=True,
        )

    async def _run_with_retry(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Run one async operation under the configured retry policy."""
        async for attempt in self._retrying():
            with attempt:
                return await operation()

        raise RuntimeError("unreachable retry state")

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allow_redirects: bool = True,
        use_proxy: bool = False,
    ) -> str:
        """HTTP GET request with retry and optional proxy.

        Args:
            url: Target URL.
            headers: Extra headers to merge with defaults.
            cookies: Cookies to send.
            params: Query parameters.
            allow_redirects: Follow redirects.
            use_proxy: Whether to route this request through the proxy.

        Returns:
            Response body as string.
        """
        async def operation() -> str:
            async with self._semaphore:
                session = await self._get_session(use_proxy=use_proxy)
                merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
                proxy_kwargs = self._get_proxy_kwargs(use_proxy)

                logger.debug(
                    "http_get",
                    url=url,
                    use_proxy=use_proxy and bool(self._proxy_url),
                )
                try:
                    async with session.get(
                        url,
                        headers=merged_headers,
                        cookies=cookies,
                        params=params,
                        allow_redirects=allow_redirects,
                        ssl=self._verify_ssl,
                        **proxy_kwargs,
                    ) as resp:
                        self._check_proxy_status(resp)
                        resp.raise_for_status()
                        return await resp.text()
                except InvalidProxyAuthError:
                    raise  # Do NOT retry 407
                except Exception as exc:
                    sanitized = self._sanitize_error(exc)
                    if "proxy" in sanitized.lower() or "socks" in sanitized.lower():
                        raise ProxyConnectionFailedError(sanitized) from exc
                    raise

        return await self._run_with_retry(operation)

    async def get_cf(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        allow_redirects: bool = True,
        use_proxy: bool = False,
    ) -> str:
        """HTTP GET with Cloudflare bypass and optional proxy.

        Strategy (layered):
          1. If cf_clearance cookie is configured → use it with aiohttp (fastest)
          2. Otherwise → try curl_cffi (handles TLS fingerprinting)
          3. If both fail → raise with clear user instructions

        Args:
            url: Target URL behind Cloudflare.
            headers: Extra headers.
            cookies: Extra cookies.
            params: Query parameters.
            allow_redirects: Follow redirects.
            use_proxy: Whether to route through proxy.

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
                    use_proxy=use_proxy,
                )
            except Exception as exc:
                logger.warning(
                    "cf_manual_failed",
                    url=url,
                    error=self._sanitize_error(exc),
                    hint="cf_clearance cookie may be expired, refresh it in config",
                )

        # Layer 2: curl_cffi (TLS fingerprint impersonation)
        from curl_cffi.requests import AsyncSession

        try:
            async with self._semaphore:
                logger.debug("http_get_cf_curl", url=url, use_proxy=use_proxy)

                # Build curl_cffi proxy config
                curl_proxies = None
                if use_proxy and self._proxy_url:
                    curl_proxies = {
                        "http": self._proxy_url,
                        "https": self._proxy_url,
                    }

                async with AsyncSession(impersonate="chrome") as s:
                    merged = {**DEFAULT_HEADERS, **(headers or {})}
                    resp = await s.get(
                        url,
                        headers=merged,
                        cookies=cookies,
                        params=params,
                        allow_redirects=allow_redirects,
                        timeout=60,
                        proxies=curl_proxies,
                    )
                    resp.raise_for_status()
                    return resp.text
        except Exception as exc:
            guidance = (
                f"To fix this:\n"
                f"1. Open {url} in your browser\n"
                f"2. Solve the Cloudflare challenge\n"
                f"3. Open DevTools (F12) -> Application -> Cookies\n"
                f"4. Copy the 'cf_clearance' cookie value\n"
                f"5. Copy your User-Agent from DevTools -> Network tab\n"
                f"6. Paste into config.yaml:\n"
                f"   javlibrary:\n"
                f"     cookie_cf_clearance: '<your_value>'\n"
                f"     browser_user_agent: '<your_ua>'\n"
                f"\n"
                f"Original error: {self._sanitize_error(exc)}"
            )
            raise CloudflareBlockedError(
                f"Cloudflare blocked access to {url}. All bypass methods failed.",
                guidance=guidance,
            ) from exc

    async def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        use_proxy: bool = False,
    ) -> Any:
        """HTTP GET and parse response as JSON with optional proxy."""
        async def operation() -> Any:
            async with self._semaphore:
                session = await self._get_session(use_proxy=use_proxy)
                merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
                proxy_kwargs = self._get_proxy_kwargs(use_proxy)

                logger.debug(
                    "http_get_json",
                    url=url,
                    use_proxy=use_proxy and bool(self._proxy_url),
                )
                try:
                    async with session.get(
                        url,
                        headers=merged_headers,
                        cookies=cookies,
                        params=params,
                        ssl=self._verify_ssl,
                        **proxy_kwargs,
                    ) as resp:
                        self._check_proxy_status(resp)
                        resp.raise_for_status()
                        return await resp.json(content_type=None)
                except InvalidProxyAuthError:
                    raise
                except Exception as exc:
                    sanitized = self._sanitize_error(exc)
                    if "proxy" in sanitized.lower() or "socks" in sanitized.lower():
                        raise ProxyConnectionFailedError(sanitized) from exc
                    raise

        return await self._run_with_retry(operation)

    async def download(
        self,
        url: str,
        dest: Path,
        cookies: dict[str, str] | None = None,
        timeout: int | None = None,
        use_proxy: bool = False,
    ) -> bool:
        """Download a file to disk with optional proxy.

        Args:
            url: URL of the file.
            dest: Destination path.
            cookies: Optional cookies.
            timeout: Override timeout for large files.
            use_proxy: Whether to route through proxy.

        Returns:
            True if download succeeded.
        """
        temp_dest = dest.with_name(f"{dest.name}.part")
        try:
            async with self._semaphore:
                session = await self._get_session(use_proxy=use_proxy)
                req_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else self.timeout
                proxy_kwargs = self._get_proxy_kwargs(use_proxy)

                logger.debug("http_download", url=url, dest=str(dest))
                async with session.get(
                    url,
                    cookies=cookies,
                    timeout=req_timeout,
                    ssl=self._verify_ssl,
                    **proxy_kwargs,
                ) as resp:
                    self._check_proxy_status(resp)
                    resp.raise_for_status()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(temp_dest, "wb") as f:
                        async for chunk in resp.content.iter_chunked(8192):
                            await f.write(chunk)
                    temp_dest.replace(dest)
            return True
        except Exception as exc:
            if temp_dest.exists():
                temp_dest.unlink()
            logger.error("http_download_failed", url=url, error=self._sanitize_error(exc))
            return False

    async def close(self) -> None:
        """Close all HTTP sessions and release connections."""
        for session in [self._session_direct, self._session_proxy]:
            if session and not session.closed:
                await session.close()
        self._session_direct = None
        self._session_proxy = None

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
