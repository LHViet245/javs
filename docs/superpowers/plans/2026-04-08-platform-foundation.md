# Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first shared platform foundation for JavS so CLI and a future API/UI can run `find`, `sort`, `update`, and settings save flows through shared application contracts backed by SQLite job and audit history.

**Architecture:** Keep `javs/core/` as the domain layer, add `javs/application/` for shared request/response contracts, add `javs/database/` and `javs/jobs/` for persistence and execution, then migrate CLI commands onto the new facade before adding thin API routes. YAML remains the active config source of truth, while SQLite stores jobs, events, items, and settings audit snapshots.

**Tech Stack:** Python 3, Typer, Pydantic, sqlite3, asyncio, pytest, Ruff

---

## File Structure

### New files

- `javs/application/__init__.py`
- `javs/application/models.py`
- `javs/application/facade.py`
- `javs/application/find.py`
- `javs/application/sort_jobs.py`
- `javs/application/update_jobs.py`
- `javs/application/settings.py`
- `javs/application/history.py`
- `javs/database/__init__.py`
- `javs/database/connection.py`
- `javs/database/schema.py`
- `javs/database/migrations.py`
- `javs/database/repositories/__init__.py`
- `javs/database/repositories/jobs.py`
- `javs/database/repositories/job_items.py`
- `javs/database/repositories/events.py`
- `javs/database/repositories/settings_audit.py`
- `javs/jobs/__init__.py`
- `javs/jobs/events.py`
- `javs/jobs/runner.py`
- `javs/jobs/executor.py`
- `javs/api/__init__.py`
- `javs/api/app.py`
- `javs/api/routes/__init__.py`
- `javs/api/routes/jobs.py`
- `javs/api/routes/settings.py`
- `tests/test_database_platform.py`
- `tests/test_application_platform.py`
- `tests/test_api_platform.py`

### Existing files to modify

- `javs/cli.py`
- `javs/core/engine.py`
- `javs/config/models.py`
- `javs/config/loader.py`
- `javs/data/default_config.yaml`
- `javs/__init__.py`
- `README.md`
- `docs/commands.md`
- `docs/configuration.md`
- `docs/contributor-guide.md`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_engine.py`

### Responsibilities

- `javs/application/models.py`: typed request/response/job/result models used by CLI and API
- `javs/application/facade.py`: main entrypoint used by CLI and API
- `javs/application/find.py`, `sort_jobs.py`, `update_jobs.py`, `settings.py`, `history.py`: focused use-case logic
- `javs/database/*`: SQLite path resolution, schema creation, migration bookkeeping, repositories
- `javs/jobs/*`: job execution, status transitions, event emission, batch execution helpers
- `javs/api/*`: thin HTTP adapter over the application facade
- `tests/test_database_platform.py`: SQLite repository and schema tests
- `tests/test_application_platform.py`: shared use-case tests
- `tests/test_api_platform.py`: API route tests

## Task 1: Add Platform Config And SQLite Path Handling

**Files:**
- Create: `javs/database/__init__.py`
- Create: `javs/database/connection.py`
- Modify: `javs/config/models.py`
- Modify: `javs/config/loader.py`
- Modify: `javs/data/default_config.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config tests**

Add tests covering a new database config surface and default SQLite path resolution.

```python
def test_database_config_defaults_are_loaded(tmp_path: Path) -> None:
    config = load_config(tmp_path / "config.yaml")
    assert config.database.enabled is True
    assert config.database.path.endswith("platform.db")


def test_database_path_can_be_overridden(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("database:\n  path: /tmp/custom.db\n", encoding="utf-8")
    config = load_config(path)
    assert config.database.path == "/tmp/custom.db"
```

- [ ] **Step 2: Run config tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_config.py -q -k database`
Expected: FAIL because `JavsConfig` has no `database` section yet.

- [ ] **Step 3: Add the minimal database config implementation**

Add a new config model in `javs/config/models.py`:

```python
class DatabaseConfig(BaseModel):
    enabled: bool = True
    path: str = "~/.javs/platform.db"
```

Attach it to `JavsConfig`, add defaults to `javs/data/default_config.yaml`, and add a helper in `javs/database/connection.py`:

```python
def resolve_database_path(config: JavsConfig) -> Path:
    return Path(config.database.path).expanduser()
```

- [ ] **Step 4: Run config tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS with existing config tests plus the new database coverage.

- [ ] **Step 5: Commit**

```bash
git add javs/config/models.py javs/config/loader.py javs/data/default_config.yaml javs/database/__init__.py javs/database/connection.py tests/test_config.py
git commit -m "feat: add platform database config"
```

## Task 2: Add SQLite Schema, Migrations, And Repository Basics

**Files:**
- Create: `javs/database/schema.py`
- Create: `javs/database/migrations.py`
- Create: `javs/database/repositories/__init__.py`
- Create: `javs/database/repositories/jobs.py`
- Create: `javs/database/repositories/job_items.py`
- Create: `javs/database/repositories/events.py`
- Create: `javs/database/repositories/settings_audit.py`
- Test: `tests/test_database_platform.py`

- [ ] **Step 1: Write the failing repository tests**

Add tests that initialize a fresh SQLite file and assert schema creation plus CRUD for the core tables.

```python
def test_initialize_platform_schema_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "platform.db"
    initialize_database(db_path)
    names = fetch_table_names(db_path)
    assert {"jobs", "job_items", "job_events", "settings_audit", "schema_migrations"} <= names


def test_job_repository_inserts_and_updates_job(tmp_path: Path) -> None:
    repo = make_job_repo(tmp_path)
    job_id = repo.create_job(kind="find", origin="cli", request_json={"movie_id": "ABP-420"})
    repo.mark_started(job_id)
    repo.mark_completed(job_id, result_json={"id": "ABP-420"})
    job = repo.get(job_id)
    assert job["status"] == "completed"
```

- [ ] **Step 2: Run the new repository tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_database_platform.py -q`
Expected: FAIL because database modules do not exist yet.

- [ ] **Step 3: Add minimal schema and repository implementation**

Implement:

- `initialize_database(path: Path) -> None`
- `apply_migrations(conn: sqlite3.Connection) -> None`
- repository methods for create/get/list/update on jobs
- item/event/settings-audit insert helpers

Keep SQL centralized in `schema.py`:

```sql
CREATE TABLE jobs (...);
CREATE TABLE job_items (...);
CREATE TABLE job_events (...);
CREATE TABLE settings_audit (...);
CREATE TABLE schema_migrations (...);
```

- [ ] **Step 4: Run repository tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_database_platform.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/database/schema.py javs/database/migrations.py javs/database/repositories/__init__.py javs/database/repositories/jobs.py javs/database/repositories/job_items.py javs/database/repositories/events.py javs/database/repositories/settings_audit.py tests/test_database_platform.py
git commit -m "feat: add platform sqlite schema and repositories"
```

## Task 3: Add Shared Application Models And Facade Skeleton

**Files:**
- Create: `javs/application/__init__.py`
- Create: `javs/application/models.py`
- Create: `javs/application/facade.py`
- Create: `javs/application/history.py`
- Test: `tests/test_application_platform.py`

- [ ] **Step 1: Write the failing application model tests**

Add tests asserting request/response contracts for jobs and settings.

```python
def test_find_request_model_normalizes_scraper_names() -> None:
    request = FindMovieRequest(movie_id="abp-420", scraper_names=["javlibrary", "dmm"])
    assert request.movie_id == "ABP-420"


def test_job_summary_response_exposes_core_fields() -> None:
    response = JobSummary(id="job-1", kind="find", status="pending", origin="cli")
    assert response.status == "pending"
```

- [ ] **Step 2: Run the application tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q`
Expected: FAIL because application modules do not exist yet.

- [ ] **Step 3: Add typed application contracts**

Implement focused Pydantic models such as:

```python
class FindMovieRequest(BaseModel):
    movie_id: str
    scraper_names: list[str] | None = None


class JobSummary(BaseModel):
    id: str
    kind: str
    status: str
    origin: str
```

Add a facade skeleton that accepts repositories and exposes method names without full execution logic yet.

- [ ] **Step 4: Run the application tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/__init__.py javs/application/models.py javs/application/facade.py javs/application/history.py tests/test_application_platform.py
git commit -m "feat: add platform application contracts"
```

## Task 4: Add In-Process Job Runner And Event Emission

**Files:**
- Create: `javs/jobs/__init__.py`
- Create: `javs/jobs/events.py`
- Create: `javs/jobs/runner.py`
- Create: `javs/jobs/executor.py`
- Modify: `javs/application/facade.py`
- Test: `tests/test_application_platform.py`

- [ ] **Step 1: Write the failing runner tests**

Add tests that verify job lifecycle transitions and event writes.

```python
async def test_runner_marks_job_running_and_completed(platform_runner) -> None:
    job_id = await platform_runner.run_find(FindMovieRequest(movie_id="ABP-420"), origin="cli")
    job = platform_runner.jobs.get(job_id)
    assert job["status"] == "completed"
    assert platform_runner.events.list_for_job(job_id)


async def test_runner_marks_job_failed_when_executor_raises(platform_runner) -> None:
    job_id = await platform_runner.run_with_executor("find", failing_executor)
    job = platform_runner.jobs.get(job_id)
    assert job["status"] == "failed"
```

- [ ] **Step 2: Run runner tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q -k runner`
Expected: FAIL because the runner and event helpers are not implemented.

- [ ] **Step 3: Implement the runner and event helpers**

Implement:

- `PlatformJobRunner`
- event helper methods such as `emit_job_created`, `emit_job_started`, `emit_job_completed`, `emit_job_failed`
- executor hooks that can wrap `JavsEngine` calls

Keep status transitions explicit and centralized:

```python
await runner.run_job(
    kind="find",
    origin="cli",
    request=request,
    executor=executor,
)
```

- [ ] **Step 4: Run runner tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py -q`
Expected: PASS with model and runner coverage.

- [ ] **Step 5: Commit**

```bash
git add javs/jobs/__init__.py javs/jobs/events.py javs/jobs/runner.py javs/jobs/executor.py javs/application/facade.py tests/test_application_platform.py
git commit -m "feat: add platform job runner"
```

## Task 5: Move `find` To The Shared Application Layer

**Files:**
- Create: `javs/application/find.py`
- Modify: `javs/application/facade.py`
- Modify: `javs/core/engine.py`
- Modify: `javs/cli.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_application_platform.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing `find` contract tests**

Add an application test for facade-backed `find`, and a CLI test that verifies the command routes through the facade path.

```python
async def test_facade_find_movie_returns_job_and_result(platform_facade) -> None:
    response = await platform_facade.find_movie(
        FindMovieRequest(movie_id="ABP-420"),
        origin="cli",
    )
    assert response.job.kind == "find"
    assert response.result.id == "ABP-420"


def test_cli_find_uses_platform_facade(runner, monkeypatch) -> None:
    ...
```

- [ ] **Step 2: Run targeted `find` tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_cli.py -q -k find`
Expected: FAIL because CLI still talks directly to `JavsEngine`.

- [ ] **Step 3: Implement `find` via application facade**

Create `javs/application/find.py` with a focused use case that:

- creates a job
- emits events
- reuses `JavsEngine.find_one()` internally
- stores the result payload in SQLite

Update CLI `find` to call the facade and then render the same output it renders today.

- [ ] **Step 4: Run targeted `find` tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_cli.py tests/test_engine.py -q -k find`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/find.py javs/application/facade.py javs/core/engine.py javs/cli.py tests/test_application_platform.py tests/test_cli.py tests/test_engine.py
git commit -m "feat: route find through platform facade"
```

## Task 6: Move `sort` And `update` To Shared Jobs

**Files:**
- Create: `javs/application/sort_jobs.py`
- Create: `javs/application/update_jobs.py`
- Modify: `javs/application/facade.py`
- Modify: `javs/cli.py`
- Modify: `javs/core/engine.py`
- Test: `tests/test_application_platform.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write the failing batch job tests**

Add tests for application-level sort/update job creation, item summaries, and CLI routing.

```python
async def test_facade_sort_creates_job_items(platform_facade, tmp_path: Path) -> None:
    response = await platform_facade.start_sort_job(...)
    assert response.job.kind == "sort"
    assert response.summary.processed >= 0


def test_cli_sort_uses_platform_facade(runner, monkeypatch) -> None:
    ...
```

- [ ] **Step 2: Run batch job tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_cli.py -q -k "sort or update"`
Expected: FAIL because `sort` and `update` are still wired directly to engine methods.

- [ ] **Step 3: Implement shared sort/update job use cases**

Use `JavsEngine.sort_path()` and `JavsEngine.update_path()` inside executor functions, but write:

- job status updates
- item records where possible
- summary payloads
- event stream entries

Update CLI `sort` and `update` to use the facade while keeping their current rendered tables and summaries.

- [ ] **Step 4: Run batch job tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_cli.py tests/test_engine.py -q -k "sort or update"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/sort_jobs.py javs/application/update_jobs.py javs/application/facade.py javs/cli.py javs/core/engine.py tests/test_application_platform.py tests/test_cli.py tests/test_engine.py
git commit -m "feat: route sort and update through platform jobs"
```

## Task 7: Add Settings Audit Through The Application Layer

**Files:**
- Create: `javs/application/settings.py`
- Modify: `javs/application/facade.py`
- Modify: `javs/config/loader.py`
- Modify: `javs/cli.py`
- Test: `tests/test_application_platform.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing settings audit tests**

Add tests for saving config through the application layer and writing settings audit rows.

```python
def test_save_settings_writes_yaml_and_audit(platform_facade, tmp_path: Path) -> None:
    response = platform_facade.save_settings(...)
    assert load_config(config_path).proxy.enabled is True
    assert settings_audit_repo.list_entries()


def test_cli_config_save_uses_platform_settings_flow(runner, monkeypatch) -> None:
    ...
```

- [ ] **Step 2: Run settings tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_config.py tests/test_cli.py -q -k settings`
Expected: FAIL because settings saves do not yet create jobs or audit entries.

- [ ] **Step 3: Implement application-backed settings save**

Implement a focused settings use case that:

- loads YAML from disk
- captures `before_json`
- applies validated changes
- saves YAML back to disk
- writes a `save_settings` job and a `settings_audit` row

- [ ] **Step 4: Run settings tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_application_platform.py tests/test_config.py tests/test_cli.py -q -k settings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/application/settings.py javs/application/facade.py javs/config/loader.py javs/cli.py tests/test_application_platform.py tests/test_config.py tests/test_cli.py
git commit -m "feat: add settings audit jobs"
```

## Task 8: Add Minimal API Over The Shared Facade

**Files:**
- Create: `javs/api/__init__.py`
- Create: `javs/api/app.py`
- Create: `javs/api/routes/__init__.py`
- Create: `javs/api/routes/jobs.py`
- Create: `javs/api/routes/settings.py`
- Modify: `javs/__init__.py`
- Test: `tests/test_api_platform.py`

- [ ] **Step 1: Write the failing API tests**

Add route tests for creating jobs and reading settings.

```python
def test_post_find_job_returns_job_payload(api_client) -> None:
    response = api_client.post("/jobs/find", json={"movie_id": "ABP-420"})
    assert response.status_code == 200
    assert response.json()["job"]["kind"] == "find"


def test_get_settings_returns_current_yaml_config(api_client) -> None:
    response = api_client.get("/settings")
    assert response.status_code == 200
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q`
Expected: FAIL because the API package does not exist.

- [ ] **Step 3: Implement the thin API layer**

Use a minimal ASGI framework already acceptable in the repo or add one small dependency only if justified. The routes should call the application facade and return serialized Pydantic payloads.

Example route shape:

```python
@router.post("/jobs/find")
async def create_find_job(payload: FindMovieRequest) -> FindMovieResponse:
    return await facade.find_movie(payload, origin="api")
```

- [ ] **Step 4: Run API tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_api_platform.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add javs/api/__init__.py javs/api/app.py javs/api/routes/__init__.py javs/api/routes/jobs.py javs/api/routes/settings.py javs/__init__.py tests/test_api_platform.py
git commit -m "feat: add platform api foundation"
```

## Task 9: Update Docs And Verification Entry Points

**Files:**
- Modify: `README.md`
- Modify: `docs/commands.md`
- Modify: `docs/configuration.md`
- Modify: `docs/contributor-guide.md`

- [ ] **Step 1: Write the failing doc expectations**

Add or update one lightweight test if needed for docs consistency, or record the required manual checks in this task:

```text
- README mentions platform foundation direction without promising full UI today
- commands docs mention shared jobs/history direction where user-visible
- contributor guide explains the new module map
```

- [ ] **Step 2: Review docs against runtime behavior**

Read:

- `README.md`
- `docs/commands.md`
- `docs/configuration.md`
- `docs/contributor-guide.md`

Expected: identify outdated CLI-direct execution descriptions.

- [ ] **Step 3: Update docs minimally and accurately**

Document:

- new platform DB config
- new application/database/jobs/api module map
- history and settings audit behavior
- current limits: no full UI yet, YAML still authoritative

- [ ] **Step 4: Run verification for docs-adjacent changes**

Run:

- `./venv/bin/python -m pytest tests/test_cli.py tests/test_config.py tests/test_application_platform.py tests/test_database_platform.py tests/test_api_platform.py -q`
- `./venv/bin/python -m ruff check javs tests`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/commands.md docs/configuration.md docs/contributor-guide.md
git commit -m "docs: document platform foundation"
```

## Task 10: Final Verification And Integration Readiness

**Files:**
- Modify as needed: only files touched by prior tasks

- [ ] **Step 1: Run full verification**

Run:

- `./scripts/verify_local.sh`
- `./venv/bin/python -m pytest tests -q`
- `./venv/bin/python -m ruff check javs tests`

Expected: PASS, or a clearly documented list of pre-existing long-running exceptions if full-suite stability still needs follow-up.

- [ ] **Step 2: Review working tree scope**

Run:

- `git status --short`
- `git diff --stat`

Expected: only intended platform foundation files are changed.

- [ ] **Step 3: Prepare integration notes**

Summarize:

- CLI parity changes
- DB schema introduction
- settings audit behavior
- API scope
- any known follow-up for UI or long-running tests

- [ ] **Step 4: Commit final cleanup if needed**

```bash
git add <any remaining intended files>
git commit -m "chore: finalize platform foundation follow-up"
```

- [ ] **Step 5: Handoff**

Use `superpowers:finishing-a-development-branch` to decide whether to merge locally, open a PR, or leave the branch for later.
