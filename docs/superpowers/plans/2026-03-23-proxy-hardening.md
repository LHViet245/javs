# Proxy Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make JavS proxy support meaningfully stronger for production-beta use by aligning config with runtime, adding a preflight command, surfacing proxy failures clearly, and only then expanding proxy routing for downloaded assets.

**Architecture:** Keep the current `HttpClient` plus per-scraper routing model. Prioritize low-risk fixes where config is currently ignored, then add lightweight diagnostics for users, and defer the only contract-expanding change until the smaller patches are already landed. Treat asset download proxy-routing as a follow-on change that should be split to avoid unnecessary model churn.

**Tech Stack:** Python 3.11+, Typer, aiohttp, tenacity, pytest, pytest-asyncio, structlog

---

## Prioritization

This plan is intentionally ordered by **ROI first**, then **risk**, then **implementation difficulty**.

- **Quick wins first:** make `proxy.max_retries` and `proxy.timeout_seconds` real before adding new UX.
- **Operational UX second:** add `javs config proxy-test` before run summaries so users can test setup proactively.
- **Field-source preservation last:** routing asset downloads through proxy requires contract changes in `MovieData` and aggregation behavior, so it is split into a smaller `5A` and optional `5B`.

Recommended execution order:

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5A
6. Task 5B if still needed
7. Task 6

### Effort / Risk / ROI Snapshot

| Task | Summary | Difficulty | Risk | ROI | Why |
| --- | --- | --- | --- | --- | --- |
| 1 | Honor `proxy.max_retries` | Low | Low | Very High | Fixes config/runtime mismatch with tiny surface area |
| 2 | Wire `proxy.timeout_seconds` | Low | Low | High | Same class of mismatch, directly user-visible |
| 3 | Add `config proxy-test` | Low-Medium | Low | High | Great support and UX value, low architecture cost |
| 4 | Add CLI proxy failure summaries | Medium | Low-Medium | Medium-High | Improves troubleshooting across commands |
| 5A | Route cover/trailer downloads via proxy | Medium-High | Medium-High | Medium | Requires model and aggregator contract changes |
| 5B | Route screenshot downloads via proxy | Medium | Medium | Medium-Low | Useful, but incremental after 5A |
| 6 | Verify and sync docs | Low | Low | Medium | Important finishing work, but not feature-driving |

### Task 1: Make `proxy.max_retries` real

**Files:**
- Modify: `javs/services/http.py`
- Test: `tests/test_proxy.py`

- [ ] **Step 1: Write the failing retry-count test for `get()`**

```python
@pytest.mark.asyncio
async def test_get_honors_configured_max_retries(monkeypatch):
    client = HttpClient(max_retries=5)
    attempts = {"count": 0}

    class BoomSession:
        def get(self, *args, **kwargs):
            attempts["count"] += 1
            raise RuntimeError("proxy unreachable")

    async def fake_get_session(use_proxy: bool = False):
        return BoomSession()

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    with pytest.raises(ProxyConnectionFailedError):
        await client.get("https://example.com", use_proxy=True)

    assert attempts["count"] == 5
```

- [ ] **Step 2: Write the matching failing retry-count test for `get_json()`**

```python
@pytest.mark.asyncio
async def test_get_json_honors_configured_max_retries(monkeypatch):
    client = HttpClient(max_retries=4)
    attempts = {"count": 0}

    class BoomSession:
        def get(self, *args, **kwargs):
            attempts["count"] += 1
            raise RuntimeError("proxy unreachable")

    async def fake_get_session(use_proxy: bool = False):
        return BoomSession()

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    with pytest.raises(ProxyConnectionFailedError):
        await client.get_json("https://example.com/api", use_proxy=True)

    assert attempts["count"] == 4
```

- [ ] **Step 3: Run just the new proxy retry tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_proxy.py -k "honors_configured_max_retries" -q
```

Expected: FAIL because retry count is still hardcoded to 3.

- [ ] **Step 4: Replace static decorators with instance-aware retry execution**

Implementation notes:
- remove the hardcoded `@retry(... stop_after_attempt(3) ...)` decorators from `get()` and `get_json()`
- add a small helper such as `_build_retrying()` or `_run_with_retry(...)`
- use `self._max_retries` instead of a literal `3`
- keep `InvalidProxyAuthError` non-retriable
- keep the same retry exception classes and exponential backoff behavior

Minimal implementation shape:

```python
from tenacity import AsyncRetrying

def _retrying(self) -> AsyncRetrying:
    return AsyncRetrying(
        stop=stop_after_attempt(self._max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        reraise=True,
    )
```

- [ ] **Step 5: Re-run the focused retry tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_proxy.py -k "honors_configured_max_retries" -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_proxy.py javs/services/http.py
git commit -m "fix: honor configured proxy retry counts"
```

### Task 2: Wire `proxy.timeout_seconds` into runtime

**Files:**
- Modify: `javs/core/engine.py`
- Modify: `javs/services/javlibrary_auth.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_javlibrary_auth.py`

- [ ] **Step 1: Write the failing engine timeout wiring test**

```python
def test_engine_uses_proxy_timeout_when_proxy_enabled(monkeypatch):
    captured = {}

    class FakeHttpClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    config = JavsConfig()
    config.proxy.enabled = True
    config.proxy.url = "http://1.2.3.4:8080"
    config.proxy.timeout_seconds = 11
    config.sort.download.timeout_seconds = 99

    monkeypatch.setattr("javs.core.engine.HttpClient", FakeHttpClient)

    JavsEngine(config)

    assert captured["timeout_seconds"] == 11
```

- [ ] **Step 2: Write the failing Javlibrary auth timeout wiring test**

```python
@pytest.mark.asyncio
async def test_validate_javlibrary_credentials_uses_proxy_timeout(monkeypatch):
    captured = {}

    class FakeHttpClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def get_cf(self, url: str, use_proxy: bool = False) -> str:
            return "<html>ok</html>"

    config = JavsConfig()
    config.proxy.enabled = True
    config.proxy.url = "http://1.2.3.4:8080"
    config.proxy.timeout_seconds = 12
    config.sort.download.timeout_seconds = 77

    monkeypatch.setattr("javs.services.javlibrary_auth.HttpClient", FakeHttpClient)

    await validate_javlibrary_credentials(config, credentials)

    assert captured["timeout_seconds"] == 12
```

- [ ] **Step 3: Run the two focused timeout tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_engine.py tests/test_javlibrary_auth.py -k "proxy_timeout" -q
```

Expected: FAIL because runtime still uses download timeout.

- [ ] **Step 4: Implement explicit timeout selection**

Implementation notes:
- when `proxy.enabled` is `True`, pass `config.proxy.timeout_seconds`
- otherwise keep current behavior using `sort.download.timeout_seconds`
- use the same rule in both `JavsEngine` and `validate_javlibrary_credentials()`

Minimal implementation shape:

```python
timeout_seconds = (
    config.proxy.timeout_seconds
    if config.proxy.enabled
    else config.sort.download.timeout_seconds
)
```

- [ ] **Step 5: Re-run the focused timeout tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_engine.py tests/test_javlibrary_auth.py -k "proxy_timeout" -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_engine.py tests/test_javlibrary_auth.py javs/core/engine.py javs/services/javlibrary_auth.py
git commit -m "fix: wire proxy timeout config into runtime"
```

### Task 3: Add `javs config proxy-test`

**Files:**
- Create: `javs/services/proxy_diagnostics.py`
- Modify: `javs/cli.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_proxy.py`
- Modify: `docs/USAGE.md`

- [ ] **Step 1: Write the failing CLI test for `config proxy-test`**

```python
def test_config_proxy_test_runs_diagnostics(monkeypatch):
    called = {}

    async def fake_run_proxy_diagnostics(config):
        called["ran"] = True
        return ProxyDiagnosticResult(ok=True, message="Proxy reachable")

    monkeypatch.setattr("javs.services.proxy_diagnostics.run_proxy_diagnostics", fake_run_proxy_diagnostics)

    result = runner.invoke(app, ["config", "proxy-test"])

    assert result.exit_code == 0
    assert "Proxy reachable" in result.stdout
    assert called["ran"] is True
```

- [ ] **Step 2: Write the failing CLI test for a failing proxy diagnostic**

```python
def test_config_proxy_test_exits_nonzero_on_failure(monkeypatch):
    ...
    assert result.exit_code == 1
```

- [ ] **Step 3: Run the focused CLI proxy-test tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_cli.py -k "proxy_test" -q
```

Expected: FAIL because the action does not exist yet.

- [ ] **Step 4: Add a small diagnostics service**

Implementation notes:
- create `ProxyDiagnosticResult`
- create async `run_proxy_diagnostics(config: JavsConfig) -> ProxyDiagnosticResult`
- validate:
  - proxy enabled
  - URL present
  - HTTP client can make one simple request through proxy
- keep the test URL injectable or module-level configurable for tests
- do not rely on live network in tests

Minimal result shape:

```python
@dataclass
class ProxyDiagnosticResult:
    ok: bool
    message: str
    detail: str = ""
```

- [ ] **Step 5: Add `proxy-test` handling in `javs config`**

Implementation notes:
- load config
- run diagnostics
- print a short success/failure summary
- exit 1 on failure

- [ ] **Step 6: Add user-facing docs**

Update `docs/USAGE.md` with one short subsection showing:

```bash
./venv/bin/javs config proxy-test
```

- [ ] **Step 7: Re-run the focused CLI proxy-test tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_cli.py -k "proxy_test" -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add tests/test_cli.py tests/test_proxy.py javs/services/proxy_diagnostics.py javs/cli.py docs/USAGE.md
git commit -m "feat: add proxy diagnostic command"
```

### Task 4: Improve CLI-facing proxy failure summaries

**Files:**
- Modify: `javs/core/engine.py`
- Modify: `javs/cli.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing engine diagnostics test**

```python
def test_find_records_proxy_failure_diagnostics(monkeypatch):
    ...
    assert engine.last_run_diagnostics == [
        {"kind": "proxy_unreachable", "scraper": "dmm"}
    ]
```

- [ ] **Step 2: Write the failing CLI summary test for `find`**

```python
def test_find_prints_proxy_failure_summary(monkeypatch):
    ...
    assert "Proxy unreachable" in result.stdout
    assert "dmm" in result.stdout
```

- [ ] **Step 3: Write the failing CLI summary test for `sort` or `update`**

```python
def test_sort_prints_proxy_failure_summary(monkeypatch, tmp_path):
    ...
    assert "Proxy failures occurred" in result.stdout
```

- [ ] **Step 4: Run the focused diagnostics summary tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_engine.py tests/test_cli.py -k "proxy_failure_summary or last_run_diagnostics" -q
```

Expected: FAIL because no run-level diagnostics summary exists yet.

- [ ] **Step 5: Add lightweight run diagnostics to `JavsEngine`**

Implementation notes:
- add `self.last_run_diagnostics: list[dict[str, str]] = []`
- reset at the start of each public run (`find_one`, `sort_path`, `update_path`)
- classify:
  - `InvalidProxyAuthError` -> `proxy_auth_failed`
  - `ProxyConnectionFailedError` -> `proxy_unreachable`
  - `CloudflareBlockedError` -> `cloudflare_blocked`
- keep only compact user-facing metadata:
  - `kind`
  - `scraper`

- [ ] **Step 6: Print a short Rich summary panel in the CLI when diagnostics exist**

Implementation notes:
- add a helper such as `_print_run_diagnostics(engine)`
- call it after `find`, `sort`, and `update`
- keep output short and user-facing, not log-heavy

Suggested output:

```text
Warnings:
- dmm: proxy unreachable
- javlibrary: Cloudflare blocked
```

- [ ] **Step 7: Re-run the focused diagnostics summary tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_engine.py tests/test_cli.py -k "proxy_failure_summary or last_run_diagnostics" -q
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add tests/test_engine.py tests/test_cli.py javs/core/engine.py javs/cli.py
git commit -m "feat: surface proxy-related failures in CLI summaries"
```

### Task 5A: Route cover and trailer downloads through proxy when the field source requires it

**Files:**
- Modify: `javs/models/movie.py`
- Modify: `javs/core/aggregator.py`
- Modify: `javs/core/organizer.py`
- Test: `tests/test_aggregator.py`
- Test: `tests/test_organizer.py`

- [ ] **Step 1: Write the failing aggregation-source test for cover and trailer fields**

```python
def test_merge_preserves_cover_and_trailer_source():
    a = MovieData(source="dmm", cover_url="https://dmm.example/cover.jpg")
    b = MovieData(source="r18dev", trailer_url="https://r18.example/trailer.mp4")

    merged = aggregator.merge([a, b])

    assert merged.cover_source == "dmm"
    assert merged.trailer_source == "r18dev"
```

- [ ] **Step 2: Write the failing organizer proxy-routing test for thumbnail download**

```python
@pytest.mark.asyncio
async def test_download_thumb_uses_proxy_when_cover_source_requires_it(tmp_path):
    config = JavsConfig()
    config.proxy.enabled = True
    config.scrapers.use_proxy["dmm"] = True

    http = FakeHttpClient()
    organizer = FileOrganizer(config, http=http)

    data = MovieData(
        id="ABP-420",
        title="Title",
        maker="Studio",
        release_date=date(2024, 1, 1),
        genres=["Demo"],
        cover_url="https://example.com/cover.jpg",
        cover_source="dmm",
    )

    await organizer._download_thumb(data, paths, force=True)

    assert http.download_calls[0]["use_proxy"] is True
```

- [ ] **Step 3: Write the matching failing organizer test for trailer download**

```python
@pytest.mark.asyncio
async def test_download_trailer_uses_proxy_when_trailer_source_requires_it(tmp_path):
    ...
    assert http.download_calls[0]["use_proxy"] is True
```

- [ ] **Step 4: Run the focused aggregation and organizer tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_aggregator.py tests/test_organizer.py -k "cover_source or trailer_source or uses_proxy_when" -q
```

Expected: FAIL because `MovieData` does not yet preserve field-level asset source.

- [ ] **Step 5: Add field-source tracking to `MovieData`**

Implementation notes:
- add nullable fields:
  - `cover_source: str | None = None`
  - `trailer_source: str | None = None`
- do not add screenshot source yet
- keep the change minimal and backward-compatible

- [ ] **Step 6: Update `DataAggregator` to preserve source names for selected fields**

Implementation notes:
- add a helper that returns both `(value, source_name)`
- use it for `cover_url` and `trailer_url`
- leave `screenshot_urls` unchanged in this task

Minimal helper shape:

```python
def _pick_field_with_source(...):
    return value, source_name
```

- [ ] **Step 7: Update `FileOrganizer` to derive `use_proxy` from field source**

Implementation notes:
- add a helper such as `_should_use_proxy_for_source(source_name: str | None) -> bool`
- use that helper in:
  - `_download_thumb()`
  - `_download_trailer()`
- keep screenshot downloads direct for now
- keep actress thumbnail downloads direct for now unless actress-thumb sources are modeled explicitly

- [ ] **Step 8: Re-run the focused aggregation and organizer tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_aggregator.py tests/test_organizer.py -k "cover_source or trailer_source or uses_proxy_when" -q
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add tests/test_aggregator.py tests/test_organizer.py javs/models/movie.py javs/core/aggregator.py javs/core/organizer.py
git commit -m "fix: route cover and trailer downloads through proxy when needed"
```

### Task 5B: Route screenshot downloads through proxy only if still needed after 5A

**Files:**
- Modify: `javs/models/movie.py`
- Modify: `javs/core/aggregator.py`
- Modify: `javs/core/organizer.py`
- Test: `tests/test_aggregator.py`
- Test: `tests/test_organizer.py`

- [ ] **Step 1: Reproduce a real failing screenshot path before changing code**

Run:

```bash
./venv/bin/python -m pytest tests/test_organizer.py -k "screenshot" -q
```

Expected: Either a new failing regression test is added first, or this task is skipped if screenshot routing is not a practical issue yet.

- [ ] **Step 2: Write the failing aggregation-source test for screenshots**

```python
def test_merge_preserves_screenshot_source():
    a = MovieData(source="dmm", screenshot_urls=["https://dmm.example/1.jpg"])
    b = MovieData(source="r18dev", screenshot_urls=["https://r18.example/1.jpg"])

    merged = aggregator.merge([a, b])

    assert merged.screenshot_source == "dmm"
```

- [ ] **Step 3: Write the failing organizer proxy-routing test for screenshot download**

```python
@pytest.mark.asyncio
async def test_download_screenshots_uses_proxy_when_source_requires_it(tmp_path):
    ...
    assert all(call["use_proxy"] is True for call in http.download_calls)
```

- [ ] **Step 4: Run the focused screenshot tests and verify they fail**

Run:

```bash
./venv/bin/python -m pytest tests/test_aggregator.py tests/test_organizer.py -k "screenshot_source or download_screenshots_uses_proxy" -q
```

Expected: FAIL because screenshot source is not modeled yet.

- [ ] **Step 5: Add screenshot source tracking**

Implementation notes:
- add `screenshot_source: str | None = None` to `MovieData`
- update `DataAggregator` to preserve source for `screenshot_urls`
- update `_download_screenshots()` to call `self.http.download(..., use_proxy=...)`

- [ ] **Step 6: Re-run the focused screenshot tests**

Run:

```bash
./venv/bin/python -m pytest tests/test_aggregator.py tests/test_organizer.py -k "screenshot_source or download_screenshots_uses_proxy" -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tests/test_aggregator.py tests/test_organizer.py javs/models/movie.py javs/core/aggregator.py javs/core/organizer.py
git commit -m "fix: route screenshot downloads through proxy when needed"
```

### Task 6: Full verification and doc sync

**Files:**
- Modify: `report.md`
- Modify: `plan.md`
- Verify: `README.md`
- Verify: `docs/USAGE.md`

- [ ] **Step 1: Run the focused test modules first**

Run:

```bash
./venv/bin/python -m pytest tests/test_proxy.py tests/test_engine.py tests/test_javlibrary_auth.py tests/test_aggregator.py tests/test_organizer.py tests/test_cli.py -q
```

Expected: PASS

- [ ] **Step 2: Run the full suite**

Run:

```bash
./venv/bin/python -m pytest tests -q
```

Expected: PASS

- [ ] **Step 3: Run lint**

Run:

```bash
./venv/bin/python -m ruff check javs tests
```

Expected: `All checks passed!`

- [ ] **Step 4: Update verification snapshot docs if behavior changed materially**

Update:
- `docs/USAGE.md` for `proxy-test`
- `report.md` if verification numbers or proxy capabilities changed
- `plan.md` to reflect completed proxy-hardening items

- [ ] **Step 5: Commit**

```bash
git add docs/USAGE.md report.md plan.md
git commit -m "docs: record proxy hardening verification"
```
