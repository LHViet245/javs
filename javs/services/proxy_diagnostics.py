"""Proxy connectivity diagnostics for CLI configuration checks."""

from __future__ import annotations

from dataclasses import dataclass

from javs.config.models import JavsConfig
from javs.services.http import HttpClient, InvalidProxyAuthError, ProxyConnectionFailedError

PROXY_TEST_URL = "https://example.com"


@dataclass(slots=True)
class ProxyDiagnosticResult:
    """User-facing result for a proxy diagnostic run."""

    ok: bool
    message: str
    detail: str = ""


async def run_proxy_diagnostics(config: JavsConfig) -> ProxyDiagnosticResult:
    """Run a minimal proxied request to validate proxy configuration."""
    if not config.proxy.enabled:
        return ProxyDiagnosticResult(ok=False, message="Proxy is disabled in config")

    proxy_url = config.proxy.url.strip()
    if not proxy_url:
        return ProxyDiagnosticResult(ok=False, message="Proxy URL is missing from config")

    client = HttpClient(
        proxy_url=proxy_url,
        timeout_seconds=config.proxy.timeout_seconds,
        max_concurrent=1,
        max_retries=config.proxy.max_retries,
        verify_ssl=False,
    )

    try:
        async with client:
            await client.get(PROXY_TEST_URL, use_proxy=True)
    except InvalidProxyAuthError as exc:
        return ProxyDiagnosticResult(
            ok=False,
            message="Proxy authentication failed",
            detail=str(exc),
        )
    except ProxyConnectionFailedError as exc:
        return ProxyDiagnosticResult(
            ok=False,
            message="Proxy unreachable",
            detail=str(exc),
        )
    except Exception as exc:
        return ProxyDiagnosticResult(
            ok=False,
            message="Proxy test failed",
            detail=str(exc),
        )

    return ProxyDiagnosticResult(ok=True, message="Proxy reachable")
