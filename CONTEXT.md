# JavS Project Context

## 1. Project Overview

**JavS** (JAV Scraper) is a modern, fast, and robust Python CLI application intended as a rewrite and successor to the original PowerShell-based Javinizer. It is designed to scrape, organize, and manage metadata and files for JAV media libraries.

### Key Technologies

- **Python 3.11+**
- **Asyncio / Aiohttp**: High-performance concurrent scraping and networking.
- **Pydantic**: Strict data modeling and configuration validation.
- **BeautifulSoup4 / lxml**: HTML/XML parsing for metadata extraction and NFO generation.
- **curl_cffi**: Advanced handling for Cloudflare IUAM/Turnstile challenges via TLS impersonation.
- **Typer & Rich**: CLI interface and beautiful terminal output.
- **structlog**: Structured JSON logging.
- **pytest**: Comprehensive testing framework (currently 96/96 tests pass).

---

## 2. Project Structure

`/home/starfall-fedora/MyApp/MyBuild/JavS/javs/`

```text
├── docs/                   # Documentation
│   └── USAGE.md            # Detailed user manual and configuration guide
├── javs/                   # Main source code
│   ├── core/               # Core engine orchestration and file operations
│   │   ├── aggregator.py   # Merges metadata from multiple scrapers based on config priorities
│   │   ├── engine.py       # Main orchestration pipeline (find, sort)
│   │   ├── organizer.py    # Pipeline for renaming, moving, and organizing files
│   │   └── scanner.py      # Regex-based scanning to extract JAV IDs from messy filenames
│   ├── data/               # Static assets and default configs
│   │   └── default_config.yaml # Base configuration file
│   ├── models/             # Pydantic data models
│   │   ├── config.py       # 15+ hierarchical configuration models
│   │   └── movie.py        # MovieData, Actress, Rating, and core data structures
│   ├── scrapers/           # Metadata scraper plugins
│   │   ├── base.py         # Abstract BaseScraper containing common logic
│   │   ├── registry.py     # Decorator-based ScraperRegistry to auto-discover scrapers
│   │   ├── dmm.py          # DMM store scraper (EN, JA)
│   │   ├── javlibrary.py   # JavLibrary scraper (EN, JA, ZH) - 12 metadata fields mapped
│   │   └── r18dev.py       # r18.dev JSON API scraper
│   ├── services/           # External service clients
│   │   ├── http.py         # Async HTTP client with retry and rate-limiting wrappers (aiohttp)
│   │   ├── image.py        # Native Poster cropping & Thumbnail generation (Pillow)
│   │   └── translation.py  # Google/DeepL translator tools
│   ├── utils/              # Helper utilities
│   │   ├── html.py         # Parsers using BeautifulSoup/lxml
│   │   ├── logging.py      # Structlog integration
│   │   └── string.py       # ID formatting, deduplication, string cleaning algorithms
│   ├── cli.py              # CLI entrypoint with Typer commands (find, sort, config, scrapers)
│   └── __main__.py         # Package execution entry point
├── tests/                  # Pytest test suite (100% Core coverage)
│   ├── scrapers/           # Specific scraper unit tests with mocked HTML fixtures
│   ├── test_aggregator.py  # Priority merging tests
│   ├── test_config.py      # YAML load/save/default fallback tests
│   ├── test_nfo.py         # lxml NFO generation tests
│   ├── test_organizer.py   # File system operation tests
│   └── test_scanner.py     # Complex regex filename scenario testing
├── README.md               # Main landing page covering features and quickstart
├── pyproject.toml          # Build config and dependency management
└── venv/                   # Local virtual environment (Mandatory execution space)
```

---

## 3. Implementation Progress

### ✅ Completed (Foundation & Modules)

- Scaffolding, dependency definitions (`pyproject.toml`), and local `venv` architecture.
- Modular Pydantic models for unified `MovieData` output.
- Custom `FileScanner` covering standard, multi-part, and obfuscated JAV ID rules.
- Decorator plugin system (`@ScraperRegistry.register`).
- Custom robust Async `http` client (`aiohttp` + `tenacity`).
- **Layered Cloudflare Bypass:** Implemented an intelligent `get_cf()` method supporting manual cookie injection (Turnstile bypass) and `curl_cffi` AsyncSession fallbacks, without blocking the async event loop.
- Comprehensive config YAML parser that gracefully falls back to defaults.
- Smart Aggregator to merge responses from any number of scrapers dynamically.
- Integration tests simulating End-to-End operations.
- **GitHub Release Readiness**: Configured `.gitignore` to protect sensitive config data, ran complete code formatting via `ruff`, verified 100% test passing, and successfully pushed the initial `main` branch to the GitHub repository (`LHViet245/javs`).

### ✅ Completed (Scrapers)

- **DMM (`dmm`, `dmmja`)**: Fully functional scraper handling cover crops and tag mapping.
- **r18.dev (`r18dev`)**: Lightweight API fallback.
- **JAVLibrary (`javlibrary`, `javlibraryja`, `javlibraryzh`)**: Fully functional. Features robust URL redirect extraction (using canonical links), Blu-ray deduplication, cross-lingual actress mapping, custom string-based rating extraction, and leverages the layered Cloudflare bypass.

### 🔄 In Progress / Next Steps

1. **Additional Scrapers**: Stubs exist for `javbus`, `javdb`, `jav321`, `mgstage`. Full parsing logic is next for these priority sites.
2. **Translation Service Integration**: Implement the deep translator for descriptions where sources lack native English text.
3. **End-to-End (E2E) Filesystem testing**: Run the `sort` engine loop on actual mocked temporary directory structures with generated mock video files.

---

## 4. Coding & Architecture Rules (MANDATORY)

1. **Virtual Environment First**: ALL commands, tests, and module installations MUST be executed using the local `./venv/bin/python` instance to prevent system contamination.
2. **Type Safety Rules Supreme**: Every piece of scraped data MUST be validated against `/models/movie.py`. `None` values are preferred over empty strings `""` for missing optional data.
3. **Regex Containment**: Avoid complex Regex when simple string manipulation works (especially against parsed HTML like `str(soup)`) to prevent backslash escaping bugs.
4. **Resilient Network Parsing**: Scrapers should use `BeautifulSoup` wrapped with `try/except` properties. A missing field should NEVER crash the entire metadata extraction process; safely return `None`.
5. **No System Dependencies**: Rely solely on pure Python dependencies or native bindings. (e.g. usage of `lxml` vs shell operations, `Pillow` vs `ImageMagick`).
6. **Aggregator Agnostic**: New scrapers MUST output uniform `MovieData`. It is the `aggregator`'s job to decide which scraper's `title` or `genres` win, based on the user's YAML config. Scrapers do not know about each other.
7. **Write Tests Concurrently**: Before closing a feature module (like a new scraper), you must provide accompanying fixtures in `/tests/` and verify that ALL previous code continues to pass.
8. **Cloudflare & Anti-Bot Awareness**: Automated solutions (like `cloudscraper` or `curl_cffi`) often fail against newer interactive JS challenges (e.g. Turnstile). Always architect bypass methods with a **Manual Fallback Layer** allowing users to supply valid `cf_clearance` cookies and user-agents from their legitimate browser sessions.
