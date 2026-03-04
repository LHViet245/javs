# JavS (JAV Scraper) - Project Context & Guidelines

## 1. Project Overview

JavS (JAV Scraper) is a modern, async Python CLI application designed to automate the organization and metadata scraping of Japanese Adult Video (JAV) files. It serves as a modern replacement for the PowerShell-based `Javinizer` project, offering better performance, cross-platform support, and easier maintenance.

- **Objective/Goal:** A Python-based CLI replacement for Javinizer.
- **Language/Core:** Python 3.11+
- **Key Characteristics:** Fully asynchronous (`asyncio`), strictly typed (`mypy`), highly modular (easy to add new scrapers), comprehensive test coverage (`pytest`).

## 2. Core Technologies & Libraries

- **Concurrency & HTTP:** `asyncio`, `aiohttp` (for general web requests), `curl_cffi` (for Cloudflare bypass), `aiohttp-socks` (for SOCKS5 proxy).
- **Configuration & Validation:** `pydantic` (for type-safe config models), `PyYAML` (for config file storage).
- **CLI Interface:** `typer` (for command parsing), `rich` (for beautiful terminal UI and progress bars).
- **HTML Parsing:** `beautifulsoup4` (with `lxml` parser).
- **Logging:** `structlog` (for structured, JSON-friendly, extensible logging).
- **Testing:** `pytest` (with `pytest-asyncio` for async tests).
- **Code Quality:** `ruff` (linting/formatting), `mypy` (strict type checking).

## 3. Project Structure

```yaml
javs/
├── pyproject.toml          # Dependencies, entry points, and build config
├── docs/                   # Documentation and usage guides
│   └── USAGE.md            # CLI usage and configuration guide
├── javs/                   # Main application package
│   ├── cli.py              # Typer CLI definition and commands
│   ├── core/               # Core workflow logic
│   │   ├── engine.py       # JavsEngine (main orchestrator)
│   │   ├── scanner.py      # FileScanner (regex ID extraction)
│   │   ├── aggregator.py   # DataAggregator (merging scraper results)
│   │   ├── nfo.py          # NfoGenerator (Emby/Kodi compatible XML)
│   │   └── organizer.py    # FileOrganizer (renaming and moving files)
│   ├── config/             # Configuration handling
│   │   ├── models.py       # Pydantic models (JavsConfig, ProxyConfig, etc.)
│   │   └── loader.py       # YAML config loader/saver
│   ├── models/             # Shared data models
│   │   ├── file.py         # FileContext (represents a file being processed)
│   │   └── movie.py        # MovieData, Actress (unified scraper output)
│   ├── scrapers/           # Metadata source scrapers
│   │   ├── base.py         # BaseScraper abstract class
│   │   ├── registry.py     # ScraperRegistry (automatic discovery/instantiation)
│   │   ├── dmm.py          # DMM scraper (with proxy default)
│   │   ├── javlibrary.py   # JavLibrary scraper (with CF bypass)
│   │   ├── r18dev.py       # R18.dev JSON API scraper
│   │   └── [others].py     # Additional future scrapers
│   ├── services/           # Utility services
│   │   ├── http.py         # HttpClient (aiohttp wrapper + retry + proxy + CF)
│   │   └── translator.py   # Translation service
│   └── utils/              # Helper functions
│       ├── logging.py      # structlog setup and custom processors (e.g., masking)
│       └── string.py       # Title cleaning, normalization
├── tests/                  # Pytest suite
│   ├── conftest.py         # Shared test fixtures
│   ├── test_config.py      # Config validation tests
│   ├── test_nfo.py         # NFO generation tests
│   ├── test_proxy.py       # Proxy config, routing, and masking tests
│   ├── test_scanner.py     # ID extraction regex tests
│   └── scrapers/           # Scraper-specific parsing tests
```

## 4. Completed Features & Implementation Status

### Core Engine

- ✅ File scanning and complex JAV ID extraction (Regex based).
- ✅ Basic CLI setup using `typer` and `rich`.
- ✅ Configuration system using `pydantic` models and YAML storage.
- ✅ Data Aggregation (merging missing fields from lower priority scrapers).
- ✅ NFO Generation (Emby/Kodi compatible).
- ✅ File Organization (Renaming and moving based on templates).

### Scrapers

- ✅ Scraper Registry (Plugin-like architecture, robust config-based routing).
- ✅ `DMM` scraper (Unified Japanese scraper returning full metadata & clean HTML entities).
- ✅ `DMM` scraper handles new SPA URLs (`video.dmm.co.jp`) via transparent API redirection and supports new `gaEventVideoStart` trailer formats.
- ✅ `JavLibrary` scraper (Includes Cloudflare bypass via `curl_cffi`).
- ✅ `R18.dev` scraper (JSON API parsing).

### Networking & Security (Proxy Integration)

- ✅ Global Proxy Configuration (`http://`, `https://`, `socks5://`, `socks5h://`).
- ✅ SOCKS5 Support via `aiohttp-socks`.
- ✅ Connection pooling (`TCPConnector(limit=100)`).
- ✅ Per-Request Proxy Routing (`use_proxy` flags per scraper).
- ✅ Default proxy routing for region-blocked scrapers (DMM, MGStage).
- ✅ Proxy Authentication handling (HTTP 407 interception, `InvalidProxyAuthError`).
- ✅ Credential Masking (Custom `structlog` processor masks proxy passwords in all logs).

### Testing

- ✅ 129 passing tests covering core logic, config, regex, NFO, proxy routing, and scraper config serialization.
- ✅ 100% pass rate with zero regression on recent proxy rewrite and scraper mergers.

## 5. Coding Guidelines & Rules

1. **Always update `pyproject.toml`** when adding new dependencies.
2. **Strict Typing:** All functions must have type hints. Use `mypy` locally to verify.
3. **Async First:** Use `async/await` for all I/O bound operations (HTTP, File System).
4. **Structured Logging:** Use `structlog` (`logger = get_logger(__name__)`). Do NOT use standard `logging` or `print` in core logic.
5. **Security:** Never log sensitive configurations (e.g., proxy passwords, API keys). Use the `MaskProxyCredentialProcessor`.
6. **Error Handling:** Use custom exceptions where appropriate (e.g., `CloudflareBlockedError`, `InvalidProxyAuthError`). Do not catch `Exception` generically without logging the traceback.
7. **Pydantic Validation:** Rely on `pydantic` for config file parsing and validation rather than manual checks.
8. **Test Driven:** Any new feature (like the proxy integration) must be accompanied by comprehensive tests in `tests/`.

## 6. Next Steps / Pending Features

- Integrate remaining scrapers (JavBus, TokyoHot, etc.).
- Implement Image/Cover downloading service and processing.
- Implement Translation service.
- Integrate with Emby APIs for automatic library refreshes.
- Enhance CLI with interactive prompt modes.
