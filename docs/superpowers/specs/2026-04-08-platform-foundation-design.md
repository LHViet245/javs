# Platform Foundation Design

## Metadata

- Date: 2026-04-08
- Status: proposed
- Scope: shared application layer, SQLite persistence, in-process jobs, and API foundation for CLI/UI parity

## Goal

Build the first platform foundation for JavS so both CLI and a future UI can use the same feature-complete workflows for:

- `find`
- `sort`
- `update`
- settings read/save
- history and audit visibility

This phase does not aim to finish a web UI. It aims to create the execution model and persistence layer that make CLI/UI parity realistic without rewriting the current domain pipeline.

## Product Direction

JavS should support two equal user types:

- users who want a full CLI workflow
- users who want a full UI workflow

Feature parity is defined at the shared application layer, not at the CLI or UI layer. A feature is only considered real when it is available through shared request/response contracts that both adapters can use.

## Non-Goals

This phase does not include:

- a full production web UI
- a distributed worker system
- replacing YAML config as the live source of truth
- moving CSV overrides such as `thumbs.csv` or `genres.csv` into the database
- broad rewrites of scraper or organizer internals

## Source Of Truth

- YAML config file remains the source of truth for active settings
- SQLite becomes the source of truth for jobs, job items, events, and settings audit history
- the filesystem remains the source of truth for media files and generated sidecars

## Architecture

### Core

`javs/core/` remains the domain layer for:

- scanning
- scraping
- aggregation
- organizing
- NFO generation
- translation

Core code should stay unaware of API, UI, database, and transport concerns.

### Application Layer

Add a new `javs/application/` layer that defines:

- request models
- response models
- use-case entrypoints
- orchestration contracts shared by CLI and API

Initial use cases:

- `find_movie`
- `start_sort_job`
- `start_update_job`
- `get_job`
- `list_jobs`
- `get_settings`
- `save_settings`

The application layer may reuse `JavsEngine` internally during the first phase, but the public contract should live in application models and facades rather than in CLI code.

### Database Layer

Add `javs/database/` for:

- SQLite connection handling
- schema creation or migrations
- repository classes for jobs, items, events, and settings audit

### Jobs Layer

Add `javs/jobs/` for:

- in-process execution
- job lifecycle updates
- event emission
- progress tracking

This is intentionally local and in-process for the first platform phase. It should be structured so that a future worker model can reuse the same contracts.

### API Layer

Add `javs/api/` as a thin adapter over the application layer.

It should expose:

- job creation
- job inspection
- settings read/save
- health endpoints if needed

Business logic must remain outside route handlers.

### CLI Layer

`javs/cli.py` should become a thin adapter over the application facade.

The CLI should keep the current user experience where practical, but the actual execution path should move to shared application contracts instead of calling engine orchestration directly.

## Execution Model

All user-facing actions in the new platform foundation should create jobs:

- `find`
- `sort`
- `update`
- `save_settings`

This keeps audit history consistent across CLI and API.

### Find

`find` remains a short-running action, but it still creates a job record and emits events.

CLI can synchronously wait for completion and print the result.
API can return the job record and allow polling or later streaming.

### Sort

`sort` becomes a job with item-level progress:

- scan source
- create item records
- process files
- emit events
- store summary

CLI can still wait and render tables.
UI can later read the same state progressively.

### Update

`update` follows the same model as `sort`, but refreshes metadata and downloads in place.

### Save Settings

`save_settings` is a short job that:

- reads the current YAML config
- applies requested changes
- validates via `JavsConfig`
- writes the YAML file
- records a settings audit snapshot in SQLite

## SQLite Schema

### `jobs`

Fields:

- `id`
- `kind`
- `status`
- `origin`
- `request_json`
- `result_json`
- `summary_json`
- `error_json`
- `created_at`
- `started_at`
- `finished_at`

Purpose:

- top-level history
- summary lists for CLI/UI
- stable storage for use-case results

### `job_items`

Fields:

- `id`
- `job_id`
- `item_key`
- `source_path`
- `dest_path`
- `movie_id`
- `status`
- `step`
- `message`
- `metadata_json`
- `error_json`
- `started_at`
- `finished_at`

Purpose:

- file-level progress for `sort` and `update`
- future item retry support
- detailed job drill-down

### `job_events`

Fields:

- `id`
- `job_id`
- `job_item_id` nullable
- `event_type`
- `payload_json`
- `created_at`

Purpose:

- audit trail
- realtime UI support later
- operational debugging

### `settings_audit`

Fields:

- `id`
- `job_id`
- `source_path`
- `config_version`
- `before_json`
- `after_json`
- `change_summary_json`
- `created_at`

Purpose:

- config save history
- settings diff support
- UI audit trail

### `schema_migrations`

Fields:

- `version`
- `applied_at`

Purpose:

- explicit schema tracking

## Module Layout

Recommended structure:

- `javs/application/models.py`
- `javs/application/facade.py`
- `javs/application/find.py`
- `javs/application/sort_jobs.py`
- `javs/application/update_jobs.py`
- `javs/application/settings.py`
- `javs/application/history.py`
- `javs/database/connection.py`
- `javs/database/schema.py`
- `javs/database/migrations.py`
- `javs/database/repositories/jobs.py`
- `javs/database/repositories/job_items.py`
- `javs/database/repositories/events.py`
- `javs/database/repositories/settings_audit.py`
- `javs/jobs/runner.py`
- `javs/jobs/events.py`
- `javs/jobs/executor.py`
- `javs/api/app.py`
- `javs/api/routes/jobs.py`
- `javs/api/routes/settings.py`

This structure keeps boundaries visible and makes it easier to reason about parity and persistence separately from scraping logic.

## Migration Strategy

### Step 1

Add SQLite schema, migrations, and repositories without changing current CLI behavior.

### Step 2

Add application request/response models and a facade that becomes the shared contract for new adapters.

### Step 3

Add an in-process job runner that can execute use cases and write jobs, items, events, and settings audit records.

### Step 4

Move CLI `find` to the application layer first, keeping the same user-facing output while storing job history.

### Step 5

Move CLI `sort` and `update` to the same application layer and job runner.

### Step 6

Move config save flows to the shared application/settings path while keeping YAML as the active source of truth.

### Step 7

Add the first API routes over the same application facade.

## Testing Strategy

Required tests for this phase:

- repository tests for SQLite create/read/update flows
- job runner tests for status and event transitions
- application tests for `find`, `sort`, `update`, and `save_settings` contracts
- CLI regression tests to confirm adapter behavior stays stable
- config tests to confirm YAML remains authoritative after settings saves

Prefer local fixtures and mocked internals over live-site behavior.

## Guardrails

- do not rewrite `JavsEngine` wholesale in the first foundation phase
- do not move CSV override datasets into SQLite yet
- do not let API routes accumulate business logic
- do not make CLI a network client in this phase
- keep request and result payloads typed rather than using unstructured ad hoc JSON
- preserve current CLI UX where possible while changing the execution path underneath

## Definition Of Done

This foundation phase is successful when:

- CLI `find`, `sort`, and `update` all run through shared application contracts
- settings saves are audited in SQLite while YAML remains the live config source
- SQLite stores jobs, items, events, and settings audit records reliably
- API endpoints exist for the same core use cases
- local verification confirms no behavior regressions in the current CLI flows

## Recommended Follow-Up

After this foundation is in place, the next phase should focus on:

- first dashboard UI slices over jobs and settings
- progress streaming or polling ergonomics
- later evaluation of database-backed override data only if the UI genuinely needs it
