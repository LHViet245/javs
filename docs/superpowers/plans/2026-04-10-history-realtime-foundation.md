# History And Realtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first history read path and realtime backend foundation for JavS so a future dashboard can list jobs, inspect job detail, read active settings, and receive live job updates over both SSE and WebSocket.

**Architecture:** Extend the existing platform foundation rather than reopening execution flows. Add typed read models and canonical read use cases in `javs/application/history.py`, extend SQLite repositories with cursor-based list/detail queries, wire `PlatformFacade` read methods, then add thin API adapters and a shared in-process event hub that fans out one logical event model to SSE and WebSocket.

**Tech Stack:** Python 3, asyncio, sqlite3, Pydantic, ASGI, httpx, pytest, Ruff

---

## File Structure

### New files

- `javs/api/routes/realtime.py`

### Existing files to modify

- `javs/application/__init__.py`
- `javs/application/history.py`
- `javs/application/models.py`
- `javs/application/facade.py`
- `javs/database/repositories/jobs.py`
- `javs/database/repositories/events.py`
- `javs/database/repositories/settings_audit.py`
- `javs/jobs/events.py`
- `javs/jobs/runner.py`
- `javs/api/app.py`
- `javs/api/routes/__init__.py`
- `javs/api/routes/jobs.py`
- `javs/api/routes/settings.py`
- `javs/cli.py`
- `tests/test_application_platform.py`
- `tests/test_database_platform.py`
- `tests/test_api_platform.py`
- `docs/commands.md`
- `docs/contributor-guide.md`

### Responsibilities

- `javs/application/history.py`: shared query models, detail/page models, realtime event model, mapper helpers, and canonical read use cases
- `javs/application/models.py`: expose history-facing response types from the main application contract surface
- `javs/application/facade.py`: implement `list_jobs()`, `get_job()`, and keep `get_settings()` aligned with read contracts
- `javs/database/repositories/jobs.py`: cursor pagination, filtering, search, and job detail query helpers
- `javs/database/repositories/events.py`: event history reads and helper methods needed by detail/realtime layers
- `javs/database/repositories/settings_audit.py`: load one audit row for a `save_settings` job
- `javs/jobs/events.py`: add shared in-process event hub and publish helpers
- `javs/jobs/runner.py`: accept and pass through the shared live event hub during real job execution
- `javs/api/routes/jobs.py`: HTTP handlers for `GET /jobs`, `GET /jobs/{id}`, and SSE entrypoint helpers
- `javs/api/routes/realtime.py`: WebSocket subscribe/fanout helpers
- `javs/api/app.py`: route HTTP and WebSocket scopes to the thin handlers
- `javs/cli.py`: bootstrap the platform facade with the same hub used by real job runs
- `tests/test_database_platform.py`: repository-level coverage for list/detail/cursor/search/event queries
- `tests/test_application_platform.py`: facade-level coverage for read contracts and realtime hub behavior
- `tests/test_api_platform.py`: API route coverage for list/detail/settings/SSE/WebSocket

## Task 1: Add Typed History Query, Detail, And Realtime Models

**Files:**
- Modify: `javs/application/__init__.py`
- Modify: `javs/application/history.py`
- Modify: `javs/application/models.py`
- Test: `tests/test_application_platform.py`

- [ ] **Step 1: Write the failing application model tests**

Add focused tests for cursor query inputs, job detail shape, and realtime event serialization.

```python
def test_job_list_query_defaults_limit_and_normalizes_filters() -> None:
    query = JobListQuery()
    assert query.limit == 20
    assert query.cursor is None


def test_job_list_page_uses_typed_summary_items() -> None:
    page = JobListPage(items=[], next_cursor=None)
    assert page.items == []


def test_history_contracts_are_reexported_from_application_package() -> None:
    from javs.application import JobListPage, JobListQuery, RealtimeEvent
    assert JobListQuery is not None
    assert JobListPage is not None
    assert RealtimeEvent is not None


def test_job_detail_allows_optional_settings_audit() -> None:
    detail = JobDetail(job=JobSummary(id="job-1", kind="sort", status="completed", origin="cli"))
    assert detail.settings_audit is None
    assert detail.events == []
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "job_list_query or job_detail_allows_optional_settings_audit"`
Expected: FAIL because the new contracts do not exist yet.

- [ ] **Step 3: Add the minimal shared history contracts**

Implement typed models in `javs/application/history.py` and re-export as needed from `javs/application/models.py`:

```python
class JobListQuery(BaseModel):
    limit: int = 20
    cursor: str | None = None
    kind: str | None = None
    status: str | None = None
    origin: str | None = None
    q: str | None = None


class RealtimeEvent(BaseModel):
    type: str
    job_id: str
    event: JobEventSummary
```

Also add explicit typed models for:

- `JobListPage`
- `SettingsView`
- `JobEventSummary`
- a normalized summary payload model or helper that guarantees stable `total`, `processed`, `skipped`, `failed`, and `warnings` keys for job list consumers

Add canonical read entrypoints in `javs/application/history.py` so facade and API code do not assemble history payloads themselves:

- `list_jobs(...)`
- `get_job_detail(...)`
- `get_settings_view(...)`

Update `javs/application/__init__.py` so the new read contracts are importable through the same package surface already used by tests and API adapters.

Extend `JobDetail` to include:

- `events`
- `settings_audit`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "job_list_query or job_detail_allows_optional_settings_audit"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/history.py javs/application/models.py tests/test_application_platform.py
git commit -m "feat: add history and realtime application contracts"
```

## Task 2: Add Repository Read Paths For Cursor Lists, Detail, And Audit

**Files:**
- Modify: `javs/database/repositories/jobs.py`
- Modify: `javs/database/repositories/events.py`
- Modify: `javs/database/repositories/settings_audit.py`
- Test: `tests/test_database_platform.py`

- [ ] **Step 1: Write the failing repository tests**

Add tests for filtered/cursor-based job listing, text search across `job_items`, detail event reads, and `settings_audit` lookup.

```python
def test_jobs_repository_lists_filtered_jobs_with_cursor(tmp_path: Path) -> None:
    repo = make_job_repo(tmp_path)
    first_id = seed_job(repo, kind="find", status="completed", origin="cli")
    second_id = seed_job(repo, kind="sort", status="running", origin="api")
    page = repo.list_jobs_page(JobListQuery(limit=1))
    assert [item["id"] for item in page.items] == [second_id]
    assert page.next_cursor is not None


def test_jobs_repository_cursor_is_stable_for_created_at_desc_id_desc_order(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)
    newest = seed_job(context.jobs, kind="sort", created_at="2026-04-10T10:00:00Z", job_id="job-b")
    older_same_time = seed_job(context.jobs, kind="sort", created_at="2026-04-10T10:00:00Z", job_id="job-a")
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1))
    second_page = context.jobs.list_jobs_page(JobListQuery(limit=1, cursor=first_page.next_cursor))
    assert [item["id"] for item in first_page.items] == [newest]
    assert [item["id"] for item in second_page.items] == [older_same_time]


def test_jobs_repository_search_matches_job_item_paths_and_movie_ids(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)
    job_id = seed_job_with_item(context, source_path="/incoming/ABP-420.mkv", movie_id="ABP-420")
    page = context.jobs.list_jobs_page(JobListQuery(q="ABP-420"))
    assert [item["id"] for item in page.items] == [job_id]


def test_jobs_repository_filters_by_status_and_origin(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="find", status="completed", origin="cli")
    target = seed_job(context.jobs, kind="sort", status="running", origin="api")
    page = context.jobs.list_jobs_page(JobListQuery(status="running", origin="api"))
    assert [item["id"] for item in page.items] == [target]


def test_jobs_repository_rejects_cursor_when_query_envelope_changes(tmp_path: Path) -> None:
    context = make_history_context(tmp_path)
    seed_job(context.jobs, kind="sort", status="running", origin="api")
    first_page = context.jobs.list_jobs_page(JobListQuery(limit=1, status="running"))
    with pytest.raises(ValueError, match="cursor"):
        context.jobs.list_jobs_page(
            JobListQuery(limit=1, cursor=first_page.next_cursor, status="completed")
        )
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_database_platform.py -q -k "cursor or search or settings_audit"`
Expected: FAIL because the repository read paths are still minimal.

- [ ] **Step 3: Implement repository list/detail/audit queries**

Add:

- cursor encoding and decoding helpers
- `list_jobs_page(query: JobListQuery) -> JobListPageRecord`
- stable ordering by `created_at DESC, id DESC`
- `limit <= 100` enforcement
- cursor rejection when the filter/search envelope does not match the query that produced it
- unique parent job results under `job_items` search matches
- `list_for_job(job_id)` in events repository
- `get_for_job(job_id)` in settings audit repository
- search coverage for `jobs.id`, `job_items.movie_id`, `job_items.source_path`, and `job_items.dest_path`

Keep SQL focused and explicit:

```sql
SELECT DISTINCT jobs.*
FROM jobs
LEFT JOIN job_items ON job_items.job_id = jobs.id
WHERE ...
ORDER BY jobs.created_at DESC, jobs.id DESC
LIMIT ?
```

- [ ] **Step 4: Run repository tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_database_platform.py -q -k "cursor or search or settings_audit"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/database/repositories/jobs.py javs/database/repositories/events.py javs/database/repositories/settings_audit.py tests/test_database_platform.py
git commit -m "feat: add history repository read paths"
```

## Task 3: Wire PlatformFacade Read APIs To Real Stored Data

**Files:**
- Modify: `javs/application/facade.py`
- Modify: `javs/application/history.py`
- Test: `tests/test_application_platform.py`

- [ ] **Step 1: Write the failing facade tests**

Add facade-level tests for:

- `list_jobs()` returning typed paginated results
- `get_job()` returning detail with events and optional settings audit
- `get_settings()` still reading YAML-backed config

```python
def test_platform_facade_lists_jobs_with_query_filters(history_facade) -> None:
    page = history_facade.list_jobs(JobListQuery(kind="sort", limit=1))
    assert len(page.items) == 1
    assert page.items[0].kind == "sort"


def test_platform_facade_get_job_includes_events_and_settings_audit(history_facade) -> None:
    detail = history_facade.get_job("job-save-1")
    assert detail is not None
    assert detail.events
    assert detail.settings_audit is not None
```

- [ ] **Step 2: Run facade tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "facade_lists_jobs or facade_get_job"`
Expected: FAIL because the facade methods still raise `NotImplementedError`.

- [ ] **Step 3: Implement facade read wiring**

Update `PlatformFacade` to:

- accept history query objects
- delegate to the canonical read use cases in `javs/application/history.py`
- keep facade methods thin rather than rebuilding history payloads inline

Keep method shapes narrow:

```python
def list_jobs(self, query: JobListQuery | None = None) -> JobListPage:
    ...


def get_job(self, job_id: str) -> JobDetail | None:
    ...
```

- [ ] **Step 4: Run facade tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "facade_lists_jobs or facade_get_job"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/facade.py javs/application/history.py tests/test_application_platform.py
git commit -m "feat: wire platform history facade reads"
```

## Task 4: Add HTTP Read Endpoints For Jobs And Settings

**Files:**
- Modify: `javs/api/routes/jobs.py`
- Modify: `javs/api/routes/settings.py`
- Modify: `javs/api/routes/__init__.py`
- Modify: `javs/api/app.py`
- Test: `tests/test_api_platform.py`

- [ ] **Step 1: Write the failing API tests**

Add route tests for:

- `GET /jobs`
- `GET /jobs/{id}`
- `GET /settings`
- `404` detail behavior for unknown job ids
- `500` settings behavior when config loading or validation fails
- max page size and search coverage for `job_id` and `dest_path`
- exact list-item `summary` counters in `GET /jobs`
- exact detail `result`, `items`, and empty-array behavior in `GET /jobs/{id}`

```python
@pytest.mark.asyncio
async def test_get_jobs_returns_filtered_page(api_app) -> None:
    response = await client.get("/jobs?kind=sort&limit=1")
    assert response.status_code == 200
    assert response.json()["items"][0]["kind"] == "sort"
    assert response.json()["items"][0]["summary"] == {
        "total": 1,
        "processed": 1,
        "skipped": 0,
        "failed": 0,
        "warnings": 0,
    }


@pytest.mark.asyncio
async def test_get_job_detail_returns_events_and_settings_audit(api_app) -> None:
    response = await client.get("/jobs/job-save-1")
    assert response.status_code == 200
    assert response.json()["settings_audit"] is not None
    assert response.json()["items"] == []
    assert response.json()["events"] == []
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "get_jobs or get_job_detail"`
Expected: FAIL because the read routes are not exposed yet.

- [ ] **Step 3: Implement the minimal read routes**

Add thin handlers:

```python
def handle_list_jobs(facade, query: Mapping[str, str]) -> JobListPage:
    return facade.list_jobs(JobListQuery.model_validate(query))


def handle_get_job_detail(facade, job_id: str) -> JobDetail | None:
    return facade.get_job(job_id)
```

Extend `JavsAPIApp` request routing so:

- `/jobs/{id}` and `/jobs` both reach these handlers
- `/settings` continues to use the shared facade read path with typed response serialization
- invalid config or validation failures in `GET /settings` produce the spec-required `500`
- `GET /settings` uses a read-specific exception branch instead of the existing global `SettingsValidationError -> 409` mapping used by write flows
- list responses serialize typed `JobListPage` data rather than raw repository dicts

- [ ] **Step 4: Run API tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "get_jobs or get_job_detail or get_and_post_settings"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/api/routes/jobs.py javs/api/routes/settings.py javs/api/routes/__init__.py javs/api/app.py tests/test_api_platform.py
git commit -m "feat: add history read api routes"
```

## Task 5: Add Shared In-Process Event Hub

**Files:**
- Modify: `javs/jobs/events.py`
- Modify: `javs/jobs/runner.py`
- Modify: `javs/cli.py`
- Modify: `tests/test_application_platform.py`

- [ ] **Step 1: Write the failing event hub tests**

Add tests for publish/subscribe behavior independent of HTTP transport.

```python
async def test_event_hub_broadcasts_live_events_to_multiple_subscribers() -> None:
    hub = EventHub()
    first = hub.subscribe()
    second = hub.subscribe()
    await hub.publish(RealtimeEvent(type="job.updated", job_id="job-1", event=event))
    assert await first.get() == await second.get()


async def test_platform_job_events_publish_to_hub_after_persistence(fake_event_repos) -> None:
    events = PlatformJobEvents(repository=fake_event_repos.repository, job_id="job-1", hub=fake_event_repos.hub)
    await events.emit("job.started", payload={"kind": "find"})
    live_event = await fake_event_repos.subscriber.get()
    assert live_event.job_id == "job-1"


async def test_platform_runner_publishes_real_job_events_to_shared_hub(platform_runtime) -> None:
    job_id = await platform_runtime.facade.find_movie(FindMovieRequest(movie_id="ABP-420"), origin="cli")
    live_event = await platform_runtime.hub_subscriber.get()
    assert live_event.job_id == job_id.job.id
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "event_hub"`
Expected: FAIL because the shared hub does not exist yet.

- [ ] **Step 3: Implement the minimal shared hub**

Add an in-process hub using subscriber queues:

```python
class EventHub:
    def subscribe(self) -> asyncio.Queue[RealtimeEvent]:
        ...

    def publish_nowait(self, event: RealtimeEvent) -> None:
        ...
```

Wire the existing persistence path so `PlatformJobEvents.emit(...)` publishes to the hub immediately after persisting a stored event row. Update `PlatformJobRunner` construction or its collaborators so real job execution paths can inject and reuse one shared hub.

Make the integration points explicit:

- `PlatformJobRunner` should accept the shared hub and pass it into per-job event helpers
- the CLI/runtime bootstrap path should construct one shared hub and thread it into the facade/runner stack used for real command execution
- `PlatformJobEvents.emit(...)` should remain synchronous; do not convert the existing event writer path to an async signature just to support live fanout
- hub fanout should happen through a synchronous helper such as `publish_nowait(...)` so existing sort/update/find executor code paths keep their current call shape
- no changes are planned for `javs/jobs/executor.py`, `javs/application/sort_jobs.py`, or `javs/application/update_jobs.py` unless implementation discovers an emit site that bypasses the runner-owned `PlatformJobEvents`

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k "event_hub"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/jobs/events.py tests/test_application_platform.py
git commit -m "feat: add shared platform event hub"
```

## Task 6: Add SSE Streaming Over The Shared Event Model

**Files:**
- Modify: `javs/api/routes/jobs.py`
- Modify: `javs/api/app.py`
- Modify: `tests/test_api_platform.py`

- [ ] **Step 1: Write the failing SSE tests**

Add tests that subscribe to:

- the global event stream
- a job-scoped stream

```python
@pytest.mark.asyncio
async def test_sse_stream_yields_global_events(api_app_with_hub) -> None:
    async with client.stream("GET", "/events/stream") as response:
        await publish_test_event(api_app_with_hub, job_id="job-1")
        body = await response.aread()
    assert b"job.updated" in body


@pytest.mark.asyncio
async def test_sse_stream_filters_to_one_job(api_app_with_hub) -> None:
    ...
```

- [ ] **Step 2: Run the SSE tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "sse_stream"`
Expected: FAIL because SSE routing and serialization do not exist yet.

- [ ] **Step 3: Implement SSE transport helpers**

Add a thin SSE serializer that emits the shared `RealtimeEvent` model:

```python
def serialize_sse_event(event: RealtimeEvent) -> bytes:
    return f"data: {event.model_dump_json()}\n\n".encode("utf-8")
```

Route `/events/stream` through a subscriber filtered by optional `job_id`.

- [ ] **Step 4: Run the SSE tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "sse_stream"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/api/routes/jobs.py javs/api/app.py tests/test_api_platform.py
git commit -m "feat: add platform sse event stream"
```

## Task 7: Add WebSocket Streaming Using The Same Event Model

**Files:**
- Create: `javs/api/routes/realtime.py`
- Modify: `javs/api/routes/__init__.py`
- Modify: `javs/api/app.py`
- Modify: `tests/test_api_platform.py`

- [ ] **Step 1: Write the failing WebSocket tests**

Add tests for:

- global subscribe with no `job_id`
- job-scoped subscribe with `job_id`
- shared event payload shape matching SSE semantics

```python
@pytest.mark.asyncio
async def test_websocket_stream_receives_global_events(api_app_with_hub) -> None:
    async with websocket_session(app, "/ws/jobs") as ws:
        await ws.send_json({"action": "subscribe"})
        await publish_test_event(...)
        message = await ws.receive_json()
    assert message["type"] == "job.updated"


@pytest.mark.asyncio
async def test_websocket_stream_filters_by_job_id(api_app_with_hub) -> None:
    ...
```

- [ ] **Step 2: Run the WebSocket tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "websocket_stream"`
Expected: FAIL because the WebSocket route does not exist yet.

- [ ] **Step 3: Implement the minimal WebSocket adapter**

Add a small route module that:

- accepts `{"action": "subscribe"}` or `{"action": "subscribe", "job_id": "..."}`
- subscribes to the shared hub
- forwards only matching events

Keep it transport-thin:

```python
async def websocket_job_stream(facade, websocket) -> None:
    subscription = await receive_subscription(websocket)
    ...
```

- [ ] **Step 4: Run the WebSocket tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q -k "websocket_stream"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/api/routes/realtime.py javs/api/routes/__init__.py javs/api/app.py tests/test_api_platform.py
git commit -m "feat: add platform websocket event stream"
```

## Task 8: Document The New History And Realtime Backend Surface

**Files:**
- Modify: `docs/commands.md`
- Modify: `docs/contributor-guide.md`

- [ ] **Step 1: Add failing doc assertions if helpful**

If the repo already uses doc regression assertions, extend them. Otherwise skip this step and document directly.

- [ ] **Step 2: Update the docs**

Document:

- the new `GET /jobs` and `GET /jobs/{id}` API surface
- the meaning of cursor pagination and filter/search parameters
- the existence of SSE and WebSocket realtime feeds
- the rule that YAML remains the active settings source of truth

- [ ] **Step 3: Review docs for consistency with the spec**

Cross-check response/parameter wording against:

- `docs/superpowers/specs/2026-04-10-history-realtime-foundation-design.md`

- [ ] **Step 4: Commit**

```bash
git add docs/commands.md docs/contributor-guide.md
git commit -m "docs: describe history and realtime backend surface"
```

## Task 9: Broad Verification And Integration Readiness

**Files:**
- Verify only

- [ ] **Step 1: Run focused database, application, and API tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_database_platform.py tests/test_application_platform.py tests/test_api_platform.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```bash
./venv/bin/python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 3: Run Ruff on app and tests**

Run:

```bash
./venv/bin/python -m ruff check javs tests
```

Expected: PASS.

- [ ] **Step 4: Inspect git scope**

Run:

```bash
git status --short
git diff --stat
```

Expected: only intended history/realtime files changed, with local untracked files outside scope left untouched.

- [ ] **Step 5: Commit any final verification-only touchups**

```bash
git add <only-files-changed-for-final-fixes>
git commit -m "test: finalize history and realtime foundation"
```

Only do this step if verification required a real code change.
