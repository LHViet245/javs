# JavS Project Context

## Overview

JavS is an async Python CLI for scraping, aggregating, and organizing JAV media libraries.
It is designed as a maintainable replacement for Javinizer, with a typed config model,
plugin-style scrapers, and a scan -> scrape -> aggregate -> organize pipeline.

## Product Capabilities

Current runtime supports:

- scanning files and extracting movie IDs from filenames
- multipart detection (`cd1`, `pt2`, `A/B`) with subtitle-suffix safeguards
- concurrent scraping from enabled sources
- priority-based metadata aggregation across scrapers
- optional metadata translation
- NFO generation for Kodi, Emby, and Jellyfin workflows
- image, poster, actress, screenshot, and trailer sidecar handling
- sorting unsorted media into a destination library
- in-place metadata refresh for already sorted libraries via `javs update`
- config sync, CSV template bootstrap, and Javlibrary credential helpers

## Architecture Map

- `javs/cli.py`: Typer CLI entrypoint and subcommands
- `javs/core/engine.py`: orchestration and shared session lifecycle
- `javs/core/scanner.py`: filename parsing and ID extraction
- `javs/core/aggregator.py`: metadata merge rules and CSV-driven enrichment
- `javs/core/organizer.py`: sidecars, downloads, moves, and update flow
- `javs/core/nfo.py`: XML generation
- `javs/config/`: pydantic models, loader, updater, deprecation helpers
- `javs/scrapers/`: source-specific search and parse implementations
- `javs/services/http.py`: shared HTTP, retry, proxy, and Cloudflare handling
- `javs/services/`: translation, image, Emby, and Javlibrary auth helpers
- `tests/`: regression suite with fixtures and sorted-output expectations

## Runtime Contracts

- Keep the app async-first. Do not introduce blocking networking where `HttpClient` already applies.
- `JavsEngine.find()` assumes an open shared `HttpClient` session.
- `JavsEngine.find_one()` manages its own session for standalone lookup.
- `JavsEngine.sort_path()` and `update_path()` share one session across the batch.
- Scrapers should focus on search and parse logic only. Shared networking belongs in `javs/services/http.py`.
- Sorting is filename-driven, not parent-directory-driven.
- Config and movie models are contracts. Normalize scraped data into typed models before passing it through the pipeline.

## Current State

The project is past the prototype stage and is usable as a real CLI.
The core pipeline, test suite, proxy routing, Cloudflare recovery flow, config sync, and update mode are in place.

Main remaining maturity work is around:

- live scraper reliability under rate limiting and Cloudflare pressure
- deeper verification of live benchmark behavior per scraper
- raising confidence in the weaker-coverage modules
- keeping docs aligned with runtime as the scraper surface evolves

## Document Roles

Use the docs in this repo by role:

- `README.md`: public project summary and quick start
- `docs/USAGE.md`: user-facing CLI and configuration guide
- `CONTEXT.md`: stable onboarding and architecture context
- `report.md`: latest audit snapshot and verification evidence
- `plan.md`: current follow-up priorities and roadmap

When docs conflict with runtime behavior, trust the code and fresh verification.
