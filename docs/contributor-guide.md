# JavS Contributor Guide

This guide is the contributor entry point for JavS. Use it when you are changing runtime behavior, adding tests, updating docs, or reviewing how the async CLI pipeline is put together.

## Who This Guide Is For

Use this guide if you are:

- contributing code or documentation
- validating a bug fix or behavior change locally
- onboarding to the project structure before making edits
- checking which repo docs are authoritative for architecture, verification, and priorities

If you only want to use JavS as an end user, start from [Getting Started](./getting-started.md) instead.

## Local Setup

From the repository root:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
./venv/bin/javs --help
```

For a broader local verification pass, run:

```bash
./scripts/verify_local.sh
```

That gives you the standard test-plus-lint entry point already used in the repo.

## Required `venv` Usage

Use the repo virtual environment for installs, tests, and app commands. The expected entry points are:

- `./venv/bin/python`
- `./venv/bin/pip`
- `./venv/bin/javs`

Do not rely on system Python or globally installed tools when reproducing or verifying repo behavior.

## Test And Lint Commands

Run the relevant checks before handoff. The standard commands are:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

For a single maintained local verification entry point, use:

```bash
./scripts/verify_local.sh
```

Prefer targeted test runs while iterating, then run the appropriate broader verification before you finish.

## Where Runtime Logic Belongs

Keep the CLI thin. `javs/cli.py` should stay focused on command wiring and user-facing options.

Put runtime behavior in the layer that owns it:

- `javs/core/`: orchestration, scanning, aggregation, organization, and NFO generation
- `javs/services/`: shared services such as HTTP, translation, image handling, Emby, and Javlibrary helpers
- `javs/scrapers/`: scraper-specific search and parse logic
- `javs/config/`: typed config models, loading, sync, and migration behavior

Important repo rules:

- keep the app async-first
- use `javs/services/http.py` for scraper and service networking
- keep scraper parsing inside scraper modules
- treat `MovieData`, `Rating`, `Actress`, and config models as contracts
- remember that sorting is filename-driven, not parent-directory-driven

## Regression Expectations

Bug fixes should come with regression coverage when practical, especially in these risk-heavy areas:

- engine lifecycle and shared-session behavior
- proxy routing and Cloudflare recovery
- scanner matching and organizer behavior
- config loading, sync, and migration behavior
- scraper parsing and aggregation decisions

Keep tests grounded in local fixtures and mocked responses rather than live-site access. Treat `tests/data/` and `tests/sorted_movies/` as deliberate regression fixtures.

Preserve the current engine lifecycle contracts:

- `JavsEngine.find()` assumes an open shared `HttpClient` session
- `JavsEngine.find_one()` manages its own session
- `sort_path()` and `update_path()` share one session across the batch

## Doc Maintenance Rules

Keep each doc focused on one role:

- [README](../README.md): public landing page and quick start
- [Getting Started](./getting-started.md): beginner-safe end-user workflow
- [Configuration](./configuration.md): practical config guide
- [Commands](./commands.md): CLI reference
- [Troubleshooting](./troubleshooting.md): symptom-based support
- [Contributor Guide](./contributor-guide.md): contributor entry point
- [USAGE](./USAGE.md): docs index kept for continuity
- [PLAYBOOK](./PLAYBOOK.md): compatibility page kept for older links

Contributor-facing durable references stay outside `docs/` as well:

- [AGENTS.md](../AGENTS.md): repository rules and workflow expectations
- [CONTEXT.md](../CONTEXT.md): stable architecture and runtime contracts
- [report.md](../report.md): latest audit snapshot and verification evidence
- [plan.md](../plan.md): current priorities and roadmap

When docs conflict with runtime behavior, trust the code and fresh local verification. When user-facing behavior or config contracts change, update the relevant focused doc instead of growing a catch-all guide.

## Project References

- [AGENTS.md](../AGENTS.md)
- [CONTEXT.md](../CONTEXT.md)
- [report.md](../report.md)
- [plan.md](../plan.md)
