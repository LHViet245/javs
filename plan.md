# JavS Current Plan

## Goal

Keep JavS stable as a production-usable CLI while improving live scraper reliability,
coverage in risk-heavy modules, and documentation hygiene.

## Recent Completed Work

The following areas are already in place and should be treated as established unless new evidence appears:

- engine session lifecycle split between `find()` and `find_one()`
- dual-session direct/proxy routing in `HttpClient`
- proxy runtime now honors configured retry counts and proxy-specific timeouts
- `javs config proxy-test` is available for proxy preflight diagnostics
- CLI warning summaries surface proxy auth, proxy reachability, and Cloudflare failures
- asset downloads now preserve field-level source for cover, trailer, and screenshots so proxy routing stays consistent after aggregation
- schema-aligned config sync and default config cleanup
- `verify_ssl` contract cleanup and regression coverage
- Javlibrary direct-match and interactive recovery improvements
- in-place metadata refresh via `javs update`
- translate pipeline hardening:
  - `affect_sort_names` added with a safe default of `false`
  - `find` keeps translated display output while `sort`/`update` can keep original naming
  - translated NFO output is covered by integration tests
  - missing translation providers now warn clearly instead of failing noisily
- lint-clean baseline and broader regression coverage

## Active Priorities

### P1. Live Scraper Reliability

- define scraper-specific expectations around retries, pacing, and rate-limit behavior
- keep measuring `dmm`, `r18dev`, `javlibrary`, and `mgstageja` with the maintained benchmark tooling
- harden user guidance and fallback behavior when live sources degrade

### P2. Coverage In High-Risk Modules

Raise confidence in modules that still combine runtime complexity with lower coverage:

- `javs/scrapers/javlibrary.py`
- `javs/utils/html.py`
- `javs/utils/logging.py`

The following risk-heavy modules improved recently and should now shift from
"missing baseline coverage" to "maintain with targeted regressions as behavior evolves":

- `javs/services/http.py`
- `javs/core/organizer.py`
- `javs/cli.py`
- `javs/services/javlibrary_auth.py`
- `javs/services/translator.py`

### P3. Product Surface Decisions

- decide whether Emby/Jellyfin integration stays as a utility service or becomes a first-class CLI workflow
- decide how much live-debug tooling under `scripts/` should remain in-repo versus be archived

### P4. Documentation Hygiene

- keep `README.md` and `docs/USAGE.md` aligned with actual CLI behavior
- keep `./scripts/verify_local.sh` as the single maintained local verification entrypoint
- keep `CONTEXT.md` architectural and stable
- keep `report.md` as the latest evidence snapshot
- keep `plan.md` short and action-oriented

## Not Now

The following ideas remain intentionally deferred because they do not currently
beat runtime hardening, config resilience, and regression coverage for ROI:

- database-backed history or metadata cache
- TUI, API server, or web UI expansion
- worker queue or job-runner architecture
- broad product-surface growth beyond the async CLI

## Guardrails

- do not refactor broad subsystems without regression coverage first
- prefer fixing contracts and behavior over adding speculative features
- treat runtime code and fresh verification as the source of truth
- use `./scripts/verify_local.sh` for the standard local test-plus-lint pass
- update the relevant doc when user-facing behavior or config contracts change

## Definition Of Progress

Meaningful progress from this point should look like one of:

- a live scraper becomes more resilient with tests and measured evidence
- a high-risk module gains targeted regression coverage
- a doc is simplified while becoming more accurate
- a stale tool, config surface, or compatibility shim is removed without losing needed behavior
