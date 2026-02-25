"""Structured logging setup using structlog."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "info", log_file: str | None = None) -> None:
    """Configure structured logging for javs.

    Args:
        level: Log level (debug, info, warning, error).
        log_file: Optional path to log file.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure structlog processors
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
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
