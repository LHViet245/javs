# History And Realtime Foundation Design

## Metadata

- Date: 2026-04-10
- Status: proposed
- Scope: job history read path, cursor-based job listing, settings read path, and shared realtime transports for dashboard foundations

## Goal

Build the first read-heavy dashboard foundation for JavS on top of the existing platform layer so a future UI can:

- list jobs with useful status and progress at a glance
- inspect full job history and item detail
- read the current active settings
- receive live updates through both SSE and WebSocket

This phase does not aim to build the full dashboard UI. It aims to finish the backend capabilities the dashboard will depend on from day one.

## Product Direction

JavS should support two equal user types:

- users who want a full CLI workflow
- users who want a full UI workflow

The platform foundation already moved command execution toward shared application contracts. This phase extends that same principle to history, inspection, and realtime visibility so CLI and UI continue to share one source of truth.

## Non-Goals

This phase does not include:

- a complete web dashboard implementation
- retry or rollback actions
- authentication or multi-user session design
- moving `thumbs.csv` or `genres.csv` into SQLite
- replacing YAML as the live settings source of truth
- transport-specific business logic that bypasses the application layer

## Required User Outcomes

After this phase:

- a dashboard can list recent jobs without polling a CLI-only path
- the list can be filtered by `kind`, `status`, and `origin`
- the list can search by `job_id`, `movie_id`, `source_path`, and `dest_path`
- the list shows useful counters such as `processed`, `skipped`, `failed`, and `warnings`
- a dashboard can open one job and inspect:
  - top-level job fields
  - result payload
  - item list
  - event stream history
  - settings audit data when the job is `save_settings`
- live job updates are available through both SSE and WebSocket using one shared event model

## Source Of Truth

- YAML config file remains the source of truth for active settings
- SQLite remains the source of truth for jobs, job items, job events, and settings audit history
- the in-process realtime hub is a live fanout mechanism, not a durable source of truth

## Architecture

### Application Layer

`javs/application/history.py` should become the main shared contract for history read behavior.

It should define typed models for:

- list query input
- paginated job list responses
- job detail responses
- realtime events
- settings view responses

It should also define read use cases used by both CLI and API:

- `list_jobs(...)`
- `get_job_detail(...)`
- `get_settings_view(...)`

### Database Layer

The current SQLite repositories should be extended with read-oriented methods for:

- cursor-based job listing
- job detail loading
- event loading
- settings audit lookup by `job_id`

Search and pagination logic belong in repositories or a closely related database query layer, not in HTTP handlers.

### Realtime Layer

The jobs subsystem should expose one shared in-process event hub.

When a job event is recorded:

1. the event is persisted to SQLite
2. the event is published to the hub in a typed live form

Both SSE and WebSocket transports subscribe to this same hub so JavS avoids maintaining two separate realtime behaviors.

### API Layer

`javs/api/` should remain a thin adapter.

It should expose:

- `GET /jobs`
- `GET /jobs/{id}`
- `GET /settings`
- `GET /events/stream` for SSE
- a WebSocket route for live job events

API routes should validate inputs, call the shared application layer, and serialize typed responses. They should not own query logic, event shaping rules, or business-specific filtering behavior.

## API Surface

### `GET /jobs`

Purpose:

- power a dashboard list view
- support CLI or API consumers that need history browsing

Query parameters:

- `limit`
- `cursor`
- `kind`
- `status`
- `origin`
- `q`

Pagination rules:

- default `limit` should be `20`
- maximum `limit` should be `100`
- a cursor is only valid when reused with the same filter and search parameters that produced it

Response shape:

```json
{
  "items": [
    {
      "id": "job-1",
      "kind": "sort",
      "status": "completed",
      "origin": "cli",
      "created_at": "2026-04-10T09:00:00Z",
      "started_at": "2026-04-10T09:00:01Z",
      "finished_at": "2026-04-10T09:00:15Z",
      "summary": {
        "total": 12,
        "processed": 10,
        "skipped": 1,
        "failed": 1,
        "warnings": 2
      },
      "error": null
    }
  ],
  "next_cursor": "opaque-cursor-or-null"
}
```

The list item must be rich enough that a dashboard can be useful without immediately opening every job detail page.

### `GET /jobs/{id}`

Purpose:

- power a dashboard detail page or side panel

Response shape:

```json
{
  "job": {
    "id": "job-1",
    "kind": "save_settings",
    "status": "completed",
    "origin": "ui",
    "created_at": "2026-04-10T09:00:00Z",
    "started_at": "2026-04-10T09:00:01Z",
    "finished_at": "2026-04-10T09:00:02Z",
    "summary": {
      "total": 1,
      "processed": 1,
      "skipped": 0,
      "failed": 0,
      "warnings": 0
    },
    "error": null
  },
  "result": {},
  "items": [],
  "events": [
    {
      "id": 10,
      "event_type": "job.started",
      "payload": {},
      "created_at": "2026-04-10T09:00:01Z"
    }
  ],
  "settings_audit": {
    "id": 3,
    "source_path": "~/.javs/config.yaml",
    "config_version": 1,
    "before": {},
    "after": {},
    "change_summary": {},
    "created_at": "2026-04-10T09:00:02Z"
  }
}
```

Rules:

- `settings_audit` is populated only for `save_settings` jobs
- `events` should be newest-last so detail views can render a natural timeline
- `items` should be stable and deterministic for the same stored job state

Error behavior:

- return `404` when the requested job id does not exist
- return `200` with empty `items` and `events` arrays when the job exists but has no item or event rows
- return `200` with `settings_audit: null` for non-`save_settings` jobs or for `save_settings` jobs that produced no audit row

### `GET /settings`

Purpose:

- power the settings screen in a future UI
- let read clients inspect the current YAML-backed configuration

Response shape:

```json
{
  "config": {},
  "source_path": "~/.javs/config.yaml",
  "config_version": 1
}
```

This endpoint reads current settings from the YAML-backed configuration path, not from a separate SQLite settings table.

Error behavior:

- return `500` if the active config file cannot be loaded or validated into the current settings view model
- do not silently fall back to a stale SQLite snapshot for live settings reads

### `GET /events/stream`

Purpose:

- provide live server-to-client updates using SSE

Query support:

- optional `job_id`

Event payload:

```json
{
  "type": "job.updated",
  "job_id": "job-1",
  "event": {
    "id": 11,
    "event_type": "job.item.completed",
    "payload": {},
    "created_at": "2026-04-10T09:00:05Z"
  }
}
```

### WebSocket Realtime Route

Purpose:

- provide the same live event model over WebSocket

The WebSocket route may accept subscription messages such as:

```json
{
  "action": "subscribe",
  "job_id": "job-1"
}
```

Global subscription may be represented as:

```json
{
  "action": "subscribe"
}
```

Rules:

- omitting `job_id` subscribes the client to the global stream
- providing `job_id` subscribes the client to one job-scoped stream
- the transport may differ, but the logical event model must match the SSE stream
- server acknowledgements, if present, should remain transport-specific metadata and must not change the shared live event payload

## Query Design

### Filters

The shared list query object should support:

- `kind`
- `status`
- `origin`
- `q`
- `limit`
- `cursor`

`q` should match against:

- job id
- `job_items.movie_id`
- `job_items.source_path`
- `job_items.dest_path`

The list response must return unique parent jobs even if multiple items match the same search query.

### Sorting And Cursor Pagination

Job lists should be ordered newest-first using:

- `created_at DESC`
- `id DESC` as a stable tiebreaker

The opaque cursor should encode:

- `created_at`
- `id`

This keeps pagination stable even when many jobs are created close together.

### Progress Counters

List views should read progress counters from each job's stored `summary_json` when available.

Expected counters:

- `total`
- `processed`
- `skipped`
- `failed`
- `warnings`

If a counter is absent in stored summary data, the typed response model may normalize it to a safe default instead of making each consumer guess.

## Realtime Design

### Shared Event Model

Define one `RealtimeEvent` model in the application layer with enough information for both list and detail views:

- top-level transport event type
- `job_id`
- serialized persisted event summary

SSE and WebSocket must both publish the same logical event content.

### Event Lifecycle

When job execution emits an event:

1. write the event to SQLite
2. publish a live `RealtimeEvent` to the in-process hub
3. let SSE and WebSocket subscribers consume that same live event

This keeps history durable while still enabling immediate UI feedback.

### Disconnect And Recovery

The first version does not need a complex replay protocol.

If a client disconnects:

- reconnect the SSE or WebSocket transport
- refetch `GET /jobs` or `GET /jobs/{id}` as needed

Durable recovery comes from the database-backed read paths, not from perfect transport-level replay.

## Module Layout

### `javs/application/history.py`

Add or expand:

- `JobListQuery`
- `JobListPage`
- `JobSummary`
- `JobDetail`
- `RealtimeEvent`
- `SettingsView`
- mapping helpers for job list/detail responses

### `javs/database/repositories/jobs.py`

Add read methods for:

- cursor-based listing
- filter application
- search joins or subqueries against `job_items`
- detail lookup for one job

### `javs/database/repositories/events.py`

Add read methods for:

- listing events for one job
- listing recent events if needed for global stream bootstrapping

### `javs/database/repositories/settings_audit.py`

Add read methods for:

- loading settings audit by `job_id`

### `javs/application/facade.py`

Implement or complete:

- `list_jobs(...)`
- `get_job(...)`
- `get_settings(...)`

These should return typed application responses rather than raw database rows.

### `javs/jobs/events.py`

Add the shared in-process event hub used by both transports.

### `javs/api/routes/jobs.py`

Add:

- `GET /jobs`
- `GET /jobs/{id}`
- `GET /events/stream`

### `javs/api/routes/settings.py`

Ensure `GET /settings` returns the shared settings view model.

### `javs/api/routes/realtime.py`

Add a WebSocket route or isolate WebSocket handling there if that keeps responsibilities clearer than extending `jobs.py`.

## Implementation Order

1. Add typed history and realtime models in the application layer
2. Implement repository read paths for list/detail/audit/event access
3. Wire `PlatformFacade.list_jobs()`, `get_job()`, and `get_settings()`
4. Add HTTP read endpoints for jobs and settings
5. Add the shared in-process event hub
6. Add the SSE transport
7. Add the WebSocket transport using the same event model and hub
8. Add tests and docs for list/detail/filter/cursor/realtime behavior

## Testing Strategy

Add regression coverage for:

- cursor pagination ordering and `next_cursor`
- filtering by `kind`, `status`, and `origin`
- text search across job id and `job_items` fields
- unique parent job behavior under multi-item matches
- job detail shape including events and optional settings audit
- settings read path from YAML-backed config
- SSE streaming for global and job-scoped subscriptions
- WebSocket streaming for global and job-scoped subscriptions
- shared event model consistency between SSE and WebSocket

Prefer local fixtures and in-memory or temp SQLite databases over live services.

## Guardrails

- do not move business query logic into API route handlers
- do not let SSE and WebSocket diverge in event payload shape
- do not make the live hub a replacement for durable history
- do not expand this phase into a full dashboard implementation
- do not introduce transport-specific behavior that the other adapter cannot reproduce

## Definition Of Done

This phase is complete when:

- `PlatformFacade.list_jobs()`, `get_job()`, and `get_settings()` work against real stored data
- `GET /jobs` supports filter, search, cursor pagination, and progress counters
- `GET /jobs/{id}` returns job detail, items, events, and optional settings audit
- both SSE and WebSocket stream the same logical live events from one shared hub
- the resulting API surface is sufficient for the first real dashboard UI to consume without inventing new backend contracts
