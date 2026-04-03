# JavS Audit Snapshot

## Scope

- Snapshot date: 2026-04-03
- Scope: current repository state after runtime seam, config migration, and verification workflow follow-up
- Focus: code health, verification status, deferred-scope discipline, and practical maturity

## Verification Snapshot

Commands used for the latest local snapshot:

```bash
./scripts/verify_local.sh
./venv/bin/javs --help
```

Latest observed results:

| Item | Result | Notes |
| --- | --- | --- |
| Test suite | `363 passed` | Fast and stable local regression suite after runtime/config hardening follow-up |
| Coverage | `82%` total | Last measured earlier; not re-run in this verification pass |
| Ruff | `All checks passed!` | Lint baseline is currently clean |
| CLI help | Main commands visible | `sort`, `update`, `find`, `config`, `scrapers` |

## Strengths

- Core architecture is cleanly layered around `scan -> scrape -> aggregate -> organize`.
- Async session lifecycle and proxy routing have been hardened with regression tests.
- Proxy config now matches runtime behavior for retries, timeouts, diagnostics, and asset downloads.
- Translation flow now supports NFO-only translation by default while keeping sort naming stable unless explicitly opted in.
- `JavsEngine` now has a lightweight runtime seam that keeps orchestration behavior intact while making dependency injection easier in tests.
- Config loading and sync now stamp a top-level `config_version` and route legacy shapes through an explicit migration helper.
- Local verification now has one maintained entrypoint in `./scripts/verify_local.sh`.
- Config sync, CSV helpers, Javlibrary credential management, and update-in-place flow are implemented.
- Scraper registry and fixture-backed scraper tests make the codebase extensible.
- The local test suite is strong enough to support refactors with reasonable confidence.

## Current Weak Spots

- Live scraper reliability still depends on external rate limits, Cloudflare behavior, and source-site churn.
- `javlibrary` remains one of the highest-risk integrations because it mixes localization, auth friction, and anti-bot behavior.
- Coverage is solid overall but still weaker in a few operational modules such as:
  - `javs/cli.py`
  - `javs/core/organizer.py`
  - `javs/services/http.py`
  - `javs/scrapers/javlibrary.py`
  - `javs/services/javlibrary_auth.py`
  - `javs/utils/html.py`
  - `javs/utils/logging.py`

## What Changed Recently

Recent repo state includes:

- `javs update` for in-place sidecar refreshes
- tighter session lifecycle boundaries in `JavsEngine`
- dual direct/proxy session handling in `HttpClient`
- proxy hardening follow-up:
  - configured retry counts and proxy timeouts now drive runtime behavior
  - `javs config proxy-test` for preflight diagnostics
  - CLI warning summaries for proxy/auth/Cloudflare failures
  - proxy-aware cover, trailer, and screenshot downloads via field-level source tracking
- translation follow-up:
  - `affect_sort_names` now controls whether translated metadata can affect folder/file naming
  - batch flows keep original naming data while writing translated NFO content by default
  - missing translation providers now surface a compact warning with install guidance
  - integration tests cover `find`, `sort`, `update`, and generated NFO output
- schema-aligned config sync and default config cleanup
- lightweight runtime/dependency seam for `JavsEngine`
- explicit config version migration pipeline
- maintained local verification script and doc alignment
- Javlibrary helper commands and interactive recovery path
- MGStage implementation plus fixture-backed tests
- workspace cleanup: canonical `AGENTS.md`, removed duplicate `.agent` rule, removed stale `scripts/real_scrape_test.py`

## Deferred Scope

The following ideas borrowed from `javinizer-go` remain intentionally deferred:

- database-backed history or metadata cache
- TUI, API server, or web UI expansion
- worker queue or job-runner architecture
- broader product-surface expansion beyond the async CLI

They are still valid ideas, but right now they do not beat runtime hardening,
config resilience, and regression coverage for return on effort. JavS gets more
value from staying sharp as a tested async CLI than from expanding into a wider
platform surface early.

## Practical Assessment

JavS is in a solid beta-like state:

- core pipeline is implemented and usable
- local quality gates are healthy
- the main remaining work is operational hardening rather than foundational architecture

This is no longer a prototype repo. The biggest risks now come from live integrations and long-tail maintenance, not from missing core product structure.
