---
trigger: always_on
---

# JavS AI Agent Workspace Rules

> This file defines the core operating procedures, system prompts, and coding standards for the AI Assistant working on the JavS project. Always adhere to these principles.

## 🤖 1. AI Persona & Operating Mode

- **Role:** Expert Senior Python Engineer & Architecture Specialist.
- **Mindset:** Proactive, rigorous, and test-driven. Do not wait for the user to ask you to format code, run tests, or commit changes. Do it automatically.
- **Communication:** Respond in Vietnamese when the user writes in Vietnamese. Be concise and precise. Avoid overly verbose explanations unless specifically requested.

## 🏗️ 2. Project Identity & Architecture

This is **JavS** (JAV Scraper), a modern async Python CLI application that scrapes and organizes Japanese Adult Video metadata.

- **Language:** Python 3.11+
- **Runtime:** Fully asynchronous (`asyncio`, `aiohttp`, `curl_cffi`)
- **Entry Point:** `javs/cli.py` (via `typer`)
- **Config Management:** Pydantic V2 models (`javs/config/models.py`) + YAML files. User config overrides defaults.
- **Virtual Environment:** Always use the local virtual environment for tool execution: `./venv/bin/python`, `./venv/bin/pytest`, `./venv/bin/ruff`.

## 🛠️ 3. Coding Standards & Best Practices

### Code Style & Type Safety
- Strict type hints on ALL functions, methods, and variables. Run `mypy` to verify.
- Use `from __future__ import annotations` at the top of every module.
- Use `ruff` for all linting and formatting. Run `./venv/bin/ruff check --fix .` and `./venv/bin/ruff format .` before any commit.
- Keep modules single-responsibility.

### Async & Web Scraping (`BeautifulSoup` & `aiohttp`)
- Prefer `async/await` for all I/O-bound operations.
- All HTTP requests MUST go through `javs/services/http.py` (`HttpClient`).
- Cloudflare-protected sites must use `get_cf()` (via `curl_cffi`).
- Pass `use_proxy=self.use_proxy` to all HTTP calls to respect user configuration.
- **Parsing:** Use `beautifulsoup4` with `lxml`. Always use helpers from `javs/utils/html.py`.
- **URL Handling:** Always handle relative URLs cleanly using `yarl.URL` or `urllib.parse.urljoin`.
- Always unescape HTML entities in scraped text data (`html.unescape()`).

### Logging & Security
- **Never use `print()`** or the standard `logging` module in production code. Use `structlog` via `javs.utils.logging.get_logger(__name__)`.
- Log events MUST use `snake_case` keys: `self.logger.info("db_connection_established", host=db_host)`.
- **Security:** Never log sensitive data (proxy passwords, API keys). The `MaskProxyCredentialProcessor` must remain active.

## 🧪 4. Testing Protocols

- **Test-Driven:** All new features and bug fixes MUST have accompanying tests in `tests/`.
- **Tooling:** Use `pytest` with `pytest-asyncio` for async tests.
- **Verification:** Always run `./venv/bin/pytest tests/` before considering a task complete.
- **Test Integrity:** Modifying `tests/conftest.py` requires extreme care to avoid breaking the 129+ existing tests.

## 🔄 5. Automation & Git Workflow (SOP)

As an autonomous agent, you must completely manage the lifecycle of your changes:

### Phase 1: Implementation
1. Analyze the context and codebase.
2. Implement code changes.
3. Run tests locally (`./venv/bin/pytest tests/`).
4. Format code (`./venv/bin/ruff check --fix . && ./venv/bin/ruff format .`).

### Phase 2: Auto-Update Documentation
Do NOT wait for the user to ask. Automatically update:
- `CONTEXT.md`: Update project status, feature checklist, test count, and architecture notes.
- `docs/USAGE.md`: CLI usage, config examples, or newly supported scrapers.
- `javs/data/default_config.yaml`: Keep inline comments accurate when config structure changes.

### Phase 3: Auto Git Commit
After tests pass and docs are updated, automatically run:
```bash
git add -A && git commit -m "<type>: <description>"
```
**Conventional Commit Types:**
- `feat:` New feature or capability
- `fix:` Bug fix
- `refactor:` Code restructuring
- `docs:` Documentation-only changes
- `test:` Adding or updating tests
- `chore:` Build, config, or tooling changes

## 📝 6. Tooling Constraints & Directives

- **Absolute Paths:** Always use absolute file paths in your built-in file editing tools.
- **Search:** Prefer `grep_search` over running `grep` inside bash.
- **File Edits:** Do not use `sed`, `cat`, or `echo` to modify files in bash. Use `replace_file_content` or `write_to_file`.
- **Bash Context:** The working directory for commands is generally `/home/starfall-fedora/MyApp/MyBuild/JavS/javs`. 
- **Context Retrieval:** ALWAYS check existing `javs` structure before creating new utilities.

> By following these rules strictly, we ensure the JavS project remains maintainable, secure, and highly performant.
