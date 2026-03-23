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

### P3. Product Surface Decisions

- decide whether Emby/Jellyfin integration stays as a utility service or becomes a first-class CLI workflow
- decide how much live-debug tooling under `scripts/` should remain in-repo versus be archived

### P4. Documentation Hygiene

- keep `README.md` and `docs/USAGE.md` aligned with actual CLI behavior
- keep `CONTEXT.md` architectural and stable
- keep `report.md` as the latest evidence snapshot
- keep `plan.md` short and action-oriented

## Guardrails

- do not refactor broad subsystems without regression coverage first
- prefer fixing contracts and behavior over adding speculative features
- treat runtime code and fresh verification as the source of truth
- update the relevant doc when user-facing behavior or config contracts change

## Definition Of Progress

Meaningful progress from this point should look like one of:

- a live scraper becomes more resilient with tests and measured evidence
- a high-risk module gains targeted regression coverage
- a doc is simplified while becoming more accurate
- a stale tool, config surface, or compatibility shim is removed without losing needed behavior
