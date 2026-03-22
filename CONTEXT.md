# JavS (JAV Scraper) - Project Context & Guidelines

## 1. Project Overview

JavS (JAV Scraper) is a modern, async Python CLI application designed to automate the organization and metadata scraping of Japanese Adult Video (JAV) files. It serves as a modern replacement for the PowerShell-based `Javinizer` project, offering better performance, cross-platform support, and easier maintenance.

- **Objective/Goal:** A Python-based CLI replacement for Javinizer.
- **Language/Core:** Python 3.11+
- **Key Characteristics:** Fully asynchronous (`asyncio`), typed with `pydantic` models and annotations, highly modular (easy to add new scrapers), and covered by a fast local `pytest` suite.

## 2. Core Technologies & Libraries

- **Concurrency & HTTP:** `asyncio`, `aiohttp` (for general web requests), `curl_cffi` (for Cloudflare bypass), `aiohttp-socks` (for SOCKS5 proxy).
- **Configuration & Validation:** `pydantic` (for type-safe config models), `ruamel.yaml` (for preserving comments locally), `PyYAML`.
- **CLI Interface:** `typer` (for command parsing), `rich` (for beautiful terminal UI and progress bars).
- **HTML Parsing:** `beautifulsoup4` (with `lxml` parser).
- **Logging:** `structlog` (for structured, JSON-friendly, extensible logging).
- **Testing:** `pytest` (with `pytest-asyncio` for async tests).
- **Code Quality:** `ruff` (linting/formatting).

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
│   │   ├── updater.py      # Config Sync (ruamel.yaml Deep Merge)
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
│   │   ├── image.py        # Image processor (Pillow cropping)
│   │   └── translator.py   # Translation service (googletrans/deepl async wrappers)
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
- ✅ File scanning now supports `auto`, `strict`, and `custom` detection modes while preserving multipart handling.
- ✅ Aggregator now supports `genres.csv` replacement/auto-add and `thumbs.csv` lookup/auto-add with package templates.
- ✅ `javs config init-csv` and `javs config csv-paths` now bootstrap and expose local CSV template paths for user curation.
- ✅ Multipart Detection: Intelligently handles part numbers (e.g. `cd1`, `pt2`, `A/B` attached to ID) while ignoring common subtitle suffixes (e.g., `-C`).
- ✅ Basic CLI setup using `typer` and `rich`.
- ✅ Configuration system using `pydantic` models and YAML storage.
- ✅ Configuration Sync (`javs config sync`): Merges the packaged default YAML into user config while preserving supported overrides and YAML comments (`ruamel.yaml`).
- ✅ Javlibrary credential helpers (`javs config javlibrary-cookie` / `javs config javlibrary-test`) for manual `cf_clearance` management and persisted `browser_user_agent` reuse.
- ✅ Data Aggregation (merging missing fields from lower priority scrapers).
- ✅ NFO Generation (Emby/Kodi compatible).
- ✅ File Organization (Renaming and moving based on templates, handles nested folder flattening and matching subtitle synchronization).
- ✅ In-place Library Refresh (`javs update`) that re-scrapes already sorted folders and rewrites metadata sidecars without moving media files.

### Scrapers

- ✅ Scraper Registry (Plugin-like architecture, robust config-based routing).
- ✅ `DMM` scraper (Unified Japanese scraper returning full metadata & clean HTML entities).
- ✅ `DMM` scraper handles new SPA URLs (`video.dmm.co.jp`) via transparent API redirection and supports new `gaEventVideoStart` trailer formats.
- ✅ `JavLibrary` scraper (Supports manual `cf_clearance`, reuses saved `browser_user_agent`, and has an interactive retry flow when Cloudflare blocks access).
- ✅ `R18.dev` scraper (JSON API parsing).

### Networking & Security (Proxy Integration)

- ✅ Global Proxy Configuration (`http://`, `https://`, `socks5://`, `socks5h://`).
- ✅ SOCKS5 Support via `aiohttp-socks`.
- ✅ Connection pooling (`TCPConnector(limit=100)`).
- ✅ Per-scraper proxy routing (`use_proxy` flags per scraper), backed by separate direct/proxy sessions in `HttpClient`.
- ✅ Default proxy routing for region-blocked scrapers (DMM, MGStage).
- ✅ Proxy Authentication handling (HTTP 407 interception, `InvalidProxyAuthError`).
- ✅ Credential Masking (Custom `structlog` processor masks proxy passwords in all logs).

### Testing

- ✅ The local pytest suite is green and covers core logic, config, regex, NFO, proxy routing, and scraper parsing with mocked/local fixtures.
- ✅ Recent fixes include `verify_ssl` semantics, config sync custom-path handling, MGStage scraping, and several regression tests around engine/runtime wiring.

## 5. Coding Guidelines & Rules

1. **Always update `pyproject.toml`** when adding new dependencies.
2. **Strict Typing:** All functions must have type hints and keep contracts explicit in the code.
3. **Async First:** Use `async/await` for all I/O bound operations (HTTP, File System).
4. **Structured Logging:** Use `structlog` (`logger = get_logger(__name__)`). Do NOT use standard `logging` or `print` in core logic.
5. **Security:** Never log sensitive configurations (e.g., proxy passwords, API keys). Use the `MaskProxyCredentialProcessor`.
6. **Error Handling:** Use custom exceptions where appropriate (e.g., `CloudflareBlockedError`, `InvalidProxyAuthError`). Do not catch `Exception` generically without logging the traceback.
7. **Pydantic Validation:** Rely on `pydantic` for config file parsing and validation rather than manual checks.
8. **Test Driven:** Any new feature (like the proxy integration) must be accompanied by comprehensive tests in `tests/`.

## 6. Next Steps / Pending Features

- Implement Image/Cover downloading service and processing.
- Integrate with Emby APIs for automatic library refreshes.
- Enhance CLI with interactive prompt modes.

## 7. Security Notes

- `HttpClient.verify_ssl` now maps directly to aiohttp's `ssl` behavior:
  - `verify_ssl=True` keeps certificate verification enabled
  - `verify_ssl=False` disables verification for that client explicitly
- `JavsEngine` currently instantiates `HttpClient(verify_ssl=False)` as a scraping trade-off.
  If more clients are added later, keep that decision explicit at each callsite.

## 8. Current State (Session Snapshot - GraviVide Branch)

**Current session snapshot:**
1. `find()` vs `find_one()` session lifecycle has been separated in `JavsEngine`.
2. `HttpClient` now uses separate direct/proxy sessions and `verify_ssl` semantics are aligned with aiohttp.
3. Config sync supports custom paths and the default template has been re-aligned with the runtime schema.
4. `mgstageja` has fixture-backed parser tests and Javlibrary direct-match handling is being tightened further.
5. `javs update` now refreshes NFO and optional assets/trailers in place for already sorted libraries.
6. Remaining priorities are rate-limit policy trade-offs, deeper live benchmarking, and smaller docs/runtime cleanup.
