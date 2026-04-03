"""Runtime construction helpers for the engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from javs.config.models import JavsConfig


@dataclass(slots=True)
class EngineRuntime:
    """Concrete runtime dependencies used by ``JavsEngine``."""

    http: Any
    scanner: Any
    aggregator: Any
    organizer: Any


def build_runtime(
    config: JavsConfig,
    *,
    http_cls: type,
    scanner_cls: type,
    aggregator_cls: type,
    organizer_cls: type,
    mask_processor: Any | None = None,
) -> EngineRuntime:
    """Build the default engine runtime from the active config."""
    proxy_url = config.proxy.url if config.proxy.enabled else None

    if proxy_url and mask_processor is not None:
        mask_processor.set_proxy_url(proxy_url, config.proxy.masked_url)

    timeout_seconds = (
        config.proxy.timeout_seconds
        if config.proxy.enabled
        else config.sort.download.timeout_seconds
    )

    http = http_cls(
        proxy_url=proxy_url,
        timeout_seconds=timeout_seconds,
        max_concurrent=config.throttle_limit * 3,
        max_retries=config.proxy.max_retries if config.proxy.enabled else 3,
        cf_clearance=config.javlibrary.cookie_cf_clearance,
        cf_user_agent=config.javlibrary.browser_user_agent,
        verify_ssl=False,
    )
    scanner = scanner_cls(config.match)
    aggregator = aggregator_cls(config)
    organizer = organizer_cls(config, http)
    return EngineRuntime(
        http=http,
        scanner=scanner,
        aggregator=aggregator,
        organizer=organizer,
    )
