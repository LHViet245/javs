---
trigger: always_on
---

# JavS Project – Workspace Rules

## Project Identity

This is **JavS** (JAV Scraper), a modern async Python CLI application that scrapes and organizes Japanese Adult Video metadata. It replaces the PowerShell-based Javinizer project.

- **Language:** Python 3.11+
- **Runtime:** Fully asynchronous (`asyncio`)
- **Entry Point:** `javs/cli.py` (via `typer`)
- **Config:** Pydantic models (`javs/config/models.py`) + YAML files (`javs/data/default_config.yaml`, `~/.javs/config.yaml`)
- **Virtual Environment:** Always use `./venv/bin/python` or `./venv/bin/pytest` for execution.

## Coding Standards

### Style & Structure

- Strict type hints on ALL functions and methods. Run `mypy` for verification.
- Use `ruff` for linting and formatting. Follow existing code style.
- Prefer `async/await` for all I/O-bound operations (HTTP, file system).
- Keep modules focused and single-responsibility. Each scraper is a self-contained class in `javs/scrapers/`.
- Use `from __future__ import annotations` at the top of every module.

### Logging & Security

- Use `structlog` via `get_logger(__name__)`. Never use `print()` or stdlib `logging` in production code.
- Never log sensitive data (proxy passwords, API keys). Use `MaskProxyCredentialProcessor` for proxy URLs.
- All log events should use snake_case keys: `self.logger.info("event_name", key=value)`.

### Configuration

- All configuration is defined via Pydantic models in `javs/config/models.py`.
- Default values live in Pydantic model defaults AND `javs/data/default_config.yaml`.
- When adding config fields: update the Pydantic model, default_config.yaml, and tests simultaneously.
- User config at `~/.javs/config.yaml` overrides defaults. Keep both in sync structurally.

### Scrapers

- All scrapers extend `BaseScraper` and are registered via `@ScraperRegistry.register`.
- Each scraper must define: `name`, `display_name`, `languages`, `base_url` as `ClassVar`.
- Scrapers must implement `async search(movie_id) -> str | None` and `async scrape(url) -> MovieData | None`.
- Pass `use_proxy=self.use_proxy` to all HTTP calls.
- HTML parsing uses `beautifulsoup4` with `lxml`. Use helpers from `javs/utils/html.py`.
- Always unescape HTML entities in scraped text data using `html.unescape()`.

### HTTP Client

- All HTTP requests go through `javs/services/http.py` (`HttpClient`).
- Cloudflare-protected sites use `get_cf()` (via `curl_cffi`).
- SOCKS5 proxy support via `aiohttp-socks`. Configured through `ProxyConfig.url`.
- Connection pooling is enabled (`TCPConnector(limit=100)`).

### Testing

- All new features must have accompanying tests in `tests/`.
- Use `pytest` with `pytest-asyncio` for async tests.
- Run tests: `./venv/bin/pytest tests`
- Current baseline: 129 passing tests, 0 failures.
- Test fixtures are defined in `tests/conftest.py`.

### Dependencies

- Always update `pyproject.toml` when adding new dependencies.
- Install in venv: `./venv/bin/pip install -e ".[dev]"`

## Key Architecture Decisions

1. **Single DMM scraper** (`dmm`): Uses Japanese site with `cklg=ja` cookies. No separate English version.
2. **Proxy per-scraper**: Each scraper has a `use_proxy` flag controlled via config. DMM and MGStage default to `True`.
3. **Data aggregation**: Multiple scrapers' results are merged by `DataAggregator` using priority lists defined in config.
4. **Plugin architecture**: Scrapers auto-register via decorator. Adding a new scraper = one new file + `@ScraperRegistry.register`.

## File Reference

| Purpose | Path |
|---|---|
| CLI commands | `javs/cli.py` |
| Main engine | `javs/core/engine.py` |
| Config models | `javs/config/models.py` |
| Config loader | `javs/config/loader.py` |
| Default config | `javs/data/default_config.yaml` |
| HTTP client | `javs/services/http.py` |
| Scraper base | `javs/scrapers/base.py` |
| Scraper registry | `javs/scrapers/registry.py` |
| DMM scraper | `javs/scrapers/dmm.py` |
| Data models | `javs/models/movie.py` |
| Logging setup | `javs/utils/logging.py` |
| Project context | `CONTEXT.md` |
| Usage guide | `docs/USAGE.md` |

## Automation Rules

### Auto-Update Documentation

After completing any code change (new feature, bug fix, refactor, config change), **automatically** update the relevant documentation files:

- `CONTEXT.md` – Update project status, feature checklist, test count, and architecture notes.
- `docs/USAGE.md` – Update CLI usage, config examples, and scraper lists if they changed.
- `default_config.yaml` comments – Keep inline comments accurate when config structure changes.
- `README.md` – Update Readme.

Do NOT wait for the user to ask. Documentation updates are part of every task completion.

### Auto Git Commit

After completing a task or a logical unit of work, **automatically** run git commit with a clear, conventional commit message:

```bash
cd /home/starfall-fedora/MyApp/MyBuild/JavS/javs && git add -A && git commit -m "<type>: <description>"
```

Commit message format (Conventional Commits):

- `feat: <description>` – New feature or capability.
- `fix: <description>` – Bug fix.
- `refactor: <description>` – Code restructuring without behavior change.
- `docs: <description>` – Documentation-only changes.
- `test: <description>` – Adding or updating tests.
- `chore: <description>` – Build, config, or tooling changes.

Examples:

- `feat: add SOCKS5 proxy support with per-scraper routing`
- `fix: unescape HTML entities in DMM genre parsing`
- `refactor: merge dmmja into unified dmm scraper`
- `docs: update CONTEXT.md with proxy integration progress`

Always commit after the documentation has been updated. One commit per logical change.

## Communication

- Respond in Vietnamese when the user writes in Vietnamese.
- Reference `CONTEXT.md` for up-to-date project status and architecture overview.
