"""Scraper registry for auto-discovery and management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from javs.utils.logging import get_logger

if TYPE_CHECKING:
    from javs.config.models import ScraperConfig
    from javs.scrapers.base import BaseScraper
    from javs.services.http import HttpClient

logger = get_logger(__name__)


class ScraperRegistry:
    """Central registry that tracks all available scraper implementations.

    Scrapers register themselves using the @register decorator.
    The engine queries the registry for enabled scrapers based on config.
    """

    _scrapers: dict[str, type[BaseScraper]] = {}

    @classmethod
    def register(cls, scraper_cls: type[BaseScraper]) -> type[BaseScraper]:
        """Decorator to register a scraper class.

        Usage:
            @ScraperRegistry.register
            class DmmScraper(BaseScraper):
                name = "dmm"
                ...

        Args:
            scraper_cls: Scraper class to register.

        Returns:
            The same class (for use as decorator).
        """
        name = scraper_cls.name
        if not name:
            raise ValueError(f"Scraper {scraper_cls.__name__} must have a 'name' class variable")

        cls._scrapers[name] = scraper_cls
        logger.debug("scraper_registered", name=name, cls=scraper_cls.__name__)
        return scraper_cls

    @classmethod
    def get_all(cls) -> dict[str, type[BaseScraper]]:
        """Return all registered scrapers."""
        return dict(cls._scrapers)

    @classmethod
    def get(cls, name: str) -> type[BaseScraper] | None:
        """Get a scraper class by name."""
        return cls._scrapers.get(name)

    @classmethod
    def get_enabled(
        cls,
        config: ScraperConfig,
        http: HttpClient | None = None,
    ) -> list[BaseScraper]:
        """Instantiate and return all enabled scrapers.

        Args:
            config: Scraper configuration with enabled flags.
            http: Shared HTTP client to use.

        Returns:
            List of instantiated scraper objects.
        """
        enabled = []
        for name, is_enabled in config.enabled.items():
            if is_enabled and name in cls._scrapers:
                scraper = cls._scrapers[name](http=http)
                enabled.append(scraper)
            elif is_enabled and name not in cls._scrapers:
                logger.warning("scraper_not_found", name=name)
        return enabled

    @classmethod
    def get_by_names(
        cls,
        names: list[str],
        http: HttpClient | None = None,
    ) -> list[BaseScraper]:
        """Instantiate scrapers by name list (for CLI override).

        Args:
            names: List of scraper names to instantiate.
            http: Shared HTTP client.

        Returns:
            List of instantiated scraper objects.
        """
        result = []
        for name in names:
            if name in cls._scrapers:
                result.append(cls._scrapers[name](http=http))
            else:
                logger.warning("scraper_not_found", name=name)
        return result

    @classmethod
    def list_names(cls) -> list[str]:
        """Return all registered scraper names."""
        return list(cls._scrapers.keys())

    @classmethod
    def load_all(cls) -> None:
        """Import all built-in scraper modules to trigger registration.

        Called once at startup to ensure all scrapers are available.
        """
        import importlib

        builtin_scrapers = [
            "javs.scrapers.dmm",
            "javs.scrapers.r18dev",
            "javs.scrapers.javlibrary",
            "javs.scrapers.javbus",
            "javs.scrapers.javdb",
            "javs.scrapers.jav321",
            "javs.scrapers.mgstage",
            "javs.scrapers.aventertainment",
            "javs.scrapers.tokyohot",
            "javs.scrapers.dlgetchu",
        ]
        for module_name in builtin_scrapers:
            try:
                importlib.import_module(module_name)
            except ImportError:
                logger.debug("scraper_module_not_found", module=module_name)
