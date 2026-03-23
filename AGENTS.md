# AGENTS.md

This file is the canonical agent guide for this repository.

- Keep `AGENTS.md` in version control.
- Prefer it over legacy workspace-specific agent rules when instructions overlap.
- Remove or update duplicate agent instruction files instead of letting them drift.

## Tooling Note

- Use the OpenAI developer documentation MCP server whenever work touches the OpenAI API, ChatGPT Apps SDK, Codex, or related OpenAI products, unless the user explicitly says otherwise.

## Project Summary

JavS is an async Python CLI for scraping, aggregating, and organizing JAV media libraries.

Core workflow:

1. Scan files and extract movie IDs from filenames
2. Query enabled scrapers concurrently
3. Merge metadata according to config priority
4. Generate assets such as NFO/poster data
5. Organize files into the destination library

Treat this as a CLI application with an async pipeline, not as a one-off scraper script.

## Environment

- Always use the local virtual environment.
- Use `./venv/bin/python`, `./venv/bin/pip`, and `./venv/bin/javs`.
- Do not use the system `python` for installs, tests, or app commands.
- Supported runtime is Python 3.11+.
- Respond in Vietnamese when the user writes in Vietnamese unless they ask otherwise.

Typical setup:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
```

Common commands:

```bash
./venv/bin/javs --help
./venv/bin/javs find "START-539"
./venv/bin/javs sort /path/to/source /path/to/dest --recurse
./venv/bin/python -m pytest tests -q
./venv/bin/python -m pytest tests/scrapers -q
./venv/bin/python -m ruff check javs tests
```

## Repository Map

- `javs/cli.py`: Typer CLI entrypoint and subcommands.
- `javs/core/engine.py`: orchestrates scan -> scrape -> aggregate -> organize.
- `javs/core/scanner.py`: filename-based movie ID extraction and multipart handling.
- `javs/core/organizer.py`: file moves, renames, sidecar handling, output layout.
- `javs/core/nfo.py`: Kodi/Emby/Jellyfin NFO generation.
- `javs/config/models.py`: `pydantic` config models.
- `javs/config/loader.py`: config load/save path handling.
- `javs/config/updater.py`: config sync/merge against `javs/data/default_config.yaml`.
- `javs/scrapers/`: site-specific scrapers registered through `ScraperRegistry`.
- `javs/services/http.py`: shared HTTP client, retries, proxy routing, Cloudflare-related handling.
- `tests/`: mocked test suite, parser fixtures, and sorted-output fixtures.
- `report.md` and `plan.md`: current audit snapshot and follow-up priorities.

## Engineering Rules

### Code Style

- Follow the existing Python style in this repo: `from __future__ import annotations`, type hints on new or changed functions, and small focused modules.
- Keep line length compatible with Ruff settings in `pyproject.toml`.
- Keep CLI code thin. Put business logic in `javs/core/`, `javs/services/`, or `javs/scrapers/` instead of growing `javs/cli.py`.
- Prefer `pathlib.Path`, explicit return types, and clear names over vague containers or ad hoc abbreviations, except established domain terms such as `nfo`, `cf`, and scraper IDs.
- Use module-level constants for fixed headers, cookie maps, regexes, and retry settings instead of rebuilding them inline.
- Keep public docstrings concise and factual, and update them when behavior changes.
- Avoid passing loose `dict[str, Any]` through the pipeline when a typed model or helper object already exists.
- Prefer explicit, domain-specific exceptions and clear error logs. Only catch broad `Exception` for true best-effort paths, and log the failure.

### Architecture And Contracts

- Preserve async-first design. Do not introduce blocking HTTP or file flows where existing async patterns already cover the use case.
- Use the shared `HttpClient` for scraper and service networking. Do not add ad hoc `aiohttp` sessions or direct `requests` calls in feature code.
- Treat `MovieData`, `Rating`, `Actress`, and config `pydantic` models as contracts. Normalize parsed data into models before passing it through the pipeline.
- Keep scraper parsing isolated inside scraper modules. Shared retry, proxy, session, and Cloudflare handling belongs in `javs/services/http.py`.
- When changing config schema, update `javs/config/models.py`, `javs/data/default_config.yaml`, the relevant runtime and CLI behavior, and the matching tests/docs together.
- When touching filesystem naming or output templates, preserve current normalization and sanitization behavior so scraped metadata cannot produce broken paths.

### Testing And Runtime

- Add regression tests for bug fixes, especially around engine lifecycle, proxy routing, scanner matching, organizer behavior, config behavior, and scraper parsing.
- Prefer local fixtures and mocked HTTP responses. Do not rely on live-site access for normal test coverage; scripts under `scripts/` are for manual debugging only.
- Treat `tests/data/` and `tests/sorted_movies/` as regression fixtures and change them only deliberately.
- Use `structlog` via `get_logger()` in library code. Avoid `print` and raw `logging` in core modules.
- Preserve engine session-lifecycle boundaries: `JavsEngine.find()` assumes an open `HttpClient` session, `find_one()` manages its own session, and `sort_path()` shares one session across the batch behind a semaphore.
- `sort` is filename-driven, not parent-directory-driven. Preserve existing `use_proxy` routing semantics in `HttpClient`.
- Prefer `javs config javlibrary-test` or the maintained benchmark scripts over one-off legacy debug scripts when validating live scraper behavior.

## Git And PR Workflow

- Check `git status --short` before broad edits and again before commit or push so you understand unrelated work in a dirty tree.
- Review `git diff --stat` before commit or push to confirm scope.
- Stage only the intended files for the current task. Do not sweep unrelated dirty-worktree changes into the same commit.
- Keep commits scoped to one concern when possible.
- Do not commit local environment files, credentials, downloaded media, logs, coverage output, or manual debugging artifacts.
- Be careful with fixture changes. If `tests/data/` or `tests/sorted_movies/` changes, make sure the matching test intent still makes sense and mention it in handoff or the PR.
- Prefer non-interactive git commands. Avoid force-push or history rewrite on shared review branches unless explicitly requested or branch policy requires it.
- Run targeted verification before commit. For broad changes, run:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

- Push the current feature branch to `origin`, then open or update the GitHub PR against the correct base branch.
- In the PR description, include a short summary, key files changed, verification run, and any known limitations or follow-up work.
- If the change affects runtime behavior, config contract, proxy handling, or scraper output, call that out explicitly in the PR.
- If CI fails, inspect the failing checks first. Fix the root cause or document why the failure is unrelated.

## Security

- Never hardcode secrets, cookies, proxy credentials, API keys, or personal paths into source files, fixtures, docs, or tracked config.
- Keep sensitive values in user-local config such as `~/.javs/config.yaml` or in environment variables.
- Preserve and extend credential masking behavior in `javs/utils/logging.py`. Never log raw proxy URLs with credentials, Cloudflare cookies, auth headers, or sensitive config dumps.
- Treat all scraped HTML, URLs, titles, and metadata as untrusted input. Parse narrowly, validate assumptions, and sanitize before using values in filenames, XML, or logs.
- Never build shell commands from scraped metadata. If external tools are needed, pass structured argument lists and sanitize file and path inputs first.
- Keep proxy and Cloudflare handling centralized in `HttpClient` and config models.
- Do not widen insecure networking behavior casually. The current `verify_ssl=False` usage is a documented trade-off; any new bypass must be narrowly scoped, justified, and documented.
- Constrain downloads and file writes to intended directories to avoid path traversal risks from remote filenames or metadata.
- Prefer least-privilege defaults: disabled integrations by default, explicit opt-in for destructive actions, and minimal persistence of sensitive data.

## Docs And Source Of Truth

- `README.md`, `docs/USAGE.md`, and `CONTEXT.md` are useful for onboarding, but some claims may lag behind the current code.
- If you need exact current behavior, trust runtime code and local verification over older prose.
- Before large refactors, read `report.md` and `plan.md` to understand current maintenance priorities and recently fixed risk areas.
- Update docs when changing user-facing behavior or config contracts.
- Keep agent-specific guidance centralized in `AGENTS.md` to avoid duplicate instructions across `.agent/`, docs, or ad hoc notes.

## Scraper Changes

- Implement new scrapers under `javs/scrapers/` and register them with `ScraperRegistry`.
- Keep scraper methods focused on search and parse behavior. Reuse normalization, HTTP, and aggregation primitives instead of duplicating them in each scraper.
- Add parser coverage under `tests/scrapers/` using local fixture HTML or mocked responses.
- Route special proxy or Cloudflare behavior through existing config and `HttpClient` paths, not ad hoc request code.

## Validation Before Handoff

- Run targeted tests for the files you changed.
- For broader changes, run:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

- State clearly what changed and what verification ran or could not run, especially if the worktree was already dirty.
