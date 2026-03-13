"""Structured logging setup using structlog with proxy credential masking."""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

# Module-level mask processor instance (singleton)
_mask_processor: MaskProxyCredentialProcessor | None = None


class MaskProxyCredentialProcessor:
    """Structlog processor that masks proxy credentials in all log output.

    Recursively scans all string values in log events and replaces
    raw proxy URLs (containing passwords) with masked versions.
    """

    def __init__(self) -> None:
        self._raw_url: str | None = None
        self._masked_url: str | None = None
        # Pattern to catch userinfo in proxy URLs even when not exact match
        self._userinfo_pattern = re.compile(r"(https?|socks[45h]*?)://([^:]+):([^@]+)@")

    def set_proxy_url(self, raw_url: str, masked_url: str) -> None:
        """Register a proxy URL and its masked counterpart.

        Args:
            raw_url: Original proxy URL with credentials.
            masked_url: URL with credentials replaced by ***.
        """
        self._raw_url = raw_url
        self._masked_url = masked_url

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Process a log event, masking any proxy credentials."""
        self._mask_recursive(event_dict)
        return event_dict

    def _mask_recursive(self, obj: Any) -> Any:
        """Recursively mask credentials in nested structures."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._mask_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._mask_recursive(item)
        elif isinstance(obj, str):
            return self._mask_string(obj)
        return obj

    def _mask_string(self, s: str) -> str:
        """Mask credentials in a single string."""
        # Exact match replacement (fastest path)
        if self._raw_url and self._masked_url and self._raw_url in s:
            s = s.replace(self._raw_url, self._masked_url)
        # Fallback: regex catch for any userinfo pattern in proxy URLs
        s = self._userinfo_pattern.sub(r"\1://***:***@", s)
        return s


def get_mask_processor() -> MaskProxyCredentialProcessor:
    """Get the global mask processor instance (lazy singleton).

    Returns:
        The shared MaskProxyCredentialProcessor.
    """
    global _mask_processor
    if _mask_processor is None:
        _mask_processor = MaskProxyCredentialProcessor()
    return _mask_processor


def setup_logging(level: str = "info", log_file: str | None = None) -> None:
    """Configure structured logging for javs.

    Args:
        level: Log level (debug, info, warning, error).
        log_file: Optional path to log file.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    mask_proc = get_mask_processor()

    # Configure structlog processors
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        # Mask proxy credentials BEFORE rendering
        mask_proc,
    ]

    if sys.stderr.isatty():
        # Pretty printing for terminal
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # JSON for log files and pipes
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging for third-party libraries
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    # If log file specified, add file handler
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name)
