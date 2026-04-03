# AGENTS.md

Repository-level instructions for Codex. Keep this file focused on durable repo rules.

## Core Expectations

- Keep `AGENTS.md` in version control and treat it as the canonical Codex guide for this repo.
- Use the OpenAI developer documentation MCP server whenever work touches the OpenAI API, ChatGPT Apps SDK, Codex, or related OpenAI products, unless the user explicitly says otherwise.
- Use the local virtual environment for installs, tests, and app commands:
  - `./venv/bin/python`
  - `./venv/bin/pip`
  - `./venv/bin/javs`
- Treat JavS as an async CLI pipeline, not as a one-off scraper script.

## Project Rules

- Keep the app async-first. Do not introduce blocking HTTP or file flows where the existing async design already applies.
- Use `javs/services/http.py` for scraper and service networking. Do not add ad hoc `aiohttp` sessions or direct `requests` calls in feature code.
- Keep scraper parsing inside scraper modules. Shared retry, proxy, session, and Cloudflare handling belongs in `javs/services/http.py`.
- Keep CLI code thin. Put business logic in `javs/core/`, `javs/services/`, or `javs/scrapers/` instead of growing `javs/cli.py`.
- Treat `MovieData`, `Rating`, `Actress`, and config `pydantic` models as contracts. Normalize parsed data into typed models before sending them through the pipeline.
- Preserve current filename normalization and sanitization behavior when changing sort paths or output templates.
- Sorting is filename-driven, not parent-directory-driven.

## Code And Config Conventions

- Follow the existing Python style: `from __future__ import annotations`, type hints on new or changed functions, small focused modules, and `pathlib.Path`.
- Prefer clear names and explicit return types over vague containers or ad hoc abbreviations, except established domain terms such as `nfo`, `cf`, and scraper IDs.
- Use module-level constants for fixed headers, cookie maps, regexes, and retry settings instead of rebuilding them inline.
- Keep public docstrings concise and factual.
- Use `structlog` via `get_logger()` in library code. Avoid `print` and raw `logging` in core modules.
- When changing config schema, update `javs/config/models.py`, `javs/data/default_config.yaml`, runtime behavior, and matching tests/docs together.

## Testing And Verification

- Add regression tests for bug fixes, especially around engine lifecycle, proxy routing, scanner matching, organizer behavior, config behavior, and scraper parsing.
- Prefer local fixtures and mocked HTTP responses. Do not rely on live-site access for normal test coverage.
- Treat `tests/data/` and `tests/sorted_movies/` as regression fixtures and change them only deliberately.
- Preserve engine session-lifecycle boundaries:
  - `JavsEngine.find()` assumes an open shared `HttpClient` session
  - `find_one()` manages its own session
  - `sort_path()` and `update_path()` share one session across the batch
- Prefer `javs config javlibrary-test` or the maintained benchmark scripts over one-off legacy debug scripts when validating live scraper behavior.
- Before handoff, run the relevant verification. For broad changes, run:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

## Git Hygiene

- Check `git status --short` before broad edits and again before commit or push.
- Review `git diff --stat` before commit or push to confirm scope.
- Stage only the intended files for the current task.
- Keep commits scoped to one concern when possible.
- Prefer non-interactive git commands.
- Do not commit credentials, downloaded media, logs, coverage output, or manual debugging artifacts.

## Security

- Never hardcode secrets, cookies, proxy credentials, API keys, or personal paths into source files, fixtures, docs, or tracked config.
- Keep sensitive values in user-local config such as `~/.javs/config.yaml` or in environment variables.
- Preserve credential masking behavior in `javs/utils/logging.py`. Never log raw proxy URLs with credentials, Cloudflare cookies, auth headers, or sensitive config dumps.
- Treat scraped HTML, URLs, titles, and metadata as untrusted input. Parse narrowly, validate assumptions, and sanitize before using values in filenames, XML, or logs.
- Keep proxy and Cloudflare handling centralized in `HttpClient` and config models.
- Do not widen insecure networking behavior casually. `verify_ssl=False` is an explicit scraping trade-off and should remain deliberate.

## Doc Routing

- `README.md`: public summary and quick start
- `docs/USAGE.md`: user-facing CLI and config guide
- `CONTEXT.md`: stable onboarding and architecture context
- `report.md`: latest audit snapshot and verification evidence
- `plan.md`: current follow-up priorities and roadmap

If docs conflict with runtime behavior, trust the code and fresh local verification.
