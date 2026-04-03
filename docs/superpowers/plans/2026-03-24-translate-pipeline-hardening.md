# Translate Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make translation behavior predictable by adding `affect_sort_names`, preserving original naming when requested, and improving translation availability warnings with integration coverage.

**Architecture:** Keep translation as a single-pass transformation near `JavsEngine.find()`, but separate which data object is used for naming versus NFO output. Add a lightweight translation preflight path so enabled-but-missing providers fail soft with explicit user guidance.

**Tech Stack:** Python 3.11, Pydantic v2, Typer, async pipeline, pytest, ruff

---

### Task 1: Add `affect_sort_names` To Config

**Files:**
- Modify: `javs/config/models.py`
- Modify: `javs/data/default_config.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add a config regression test asserting `TranslateConfig().affect_sort_names is False` and that loading/saving config preserves the field.

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_config.py -k affect_sort_names -q`
Expected: FAIL because the field does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add `affect_sort_names: bool = False` to `TranslateConfig` and mirror it in `default_config.yaml`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_config.py -k affect_sort_names -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/config/models.py javs/data/default_config.yaml tests/test_config.py
git commit -m "feat: add translate affect_sort_names option"
```

### Task 2: Separate Naming Data From NFO Data

**Files:**
- Modify: `javs/core/engine.py`
- Modify: `javs/core/organizer.py`
- Possibly Modify: `javs/models/movie.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_organizer.py`

- [ ] **Step 1: Write the failing tests**

Add focused tests for:
- `find()` returns translated metadata when translation is enabled
- `sort_path()` keeps original naming when `affect_sort_names` is `false`
- `update_path()` writes translated NFO content without changing naming assumptions

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_engine.py tests/test_organizer.py -k "translate and affect_sort_names" -q`
Expected: FAIL because current pipeline mutates one shared object for all consumers.

- [ ] **Step 3: Write minimal implementation**

Implement a single-pass translation flow:
- produce translated metadata once after aggregation
- for `find`, return translated data
- for `sort/update`, keep original data for naming when `affect_sort_names` is `false`
- teach organizer/NFO writing to accept translated NFO data separately when needed

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_engine.py tests/test_organizer.py -k "translate and affect_sort_names" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/core/engine.py javs/core/organizer.py javs/models/movie.py tests/test_engine.py tests/test_organizer.py
git commit -m "fix: separate translate naming from nfo output"
```

### Task 3: Add Translation Provider Preflight Warnings

**Files:**
- Modify: `javs/services/translator.py`
- Modify: `javs/cli.py` or `javs/core/engine.py` if warnings need surfacing there
- Test: `tests/test_translator.py`
- Test: `tests/test_cli.py` or `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving that when translation is enabled and the provider package is missing:
- translation returns safely without crashing
- a compact user-facing warning/install hint is available

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_translator.py tests/test_cli.py tests/test_engine.py -k "translate and missing provider" -q`
Expected: FAIL because current behavior only logs internal errors.

- [ ] **Step 3: Write minimal implementation**

Add a small preflight helper that checks provider availability and returns a warning message/hint. Surface it once per command run rather than per field.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_translator.py tests/test_cli.py tests/test_engine.py -k "translate and missing provider" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/services/translator.py javs/cli.py javs/core/engine.py tests/test_translator.py tests/test_cli.py tests/test_engine.py
git commit -m "feat: warn when translation provider is unavailable"
```

### Task 4: Add Integration Coverage For NFO Translation

**Files:**
- Modify: `tests/test_nfo.py`
- Modify: `tests/test_organizer.py`
- Possibly Modify: `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Add end-to-end style tests showing:
- translated `description` lands in generated NFO
- original title still drives path naming when `affect_sort_names` is `false`
- translated title affects naming only when `affect_sort_names` is `true`

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_nfo.py tests/test_organizer.py tests/test_engine.py -k "translate" -q`
Expected: FAIL until the pipeline boundary is correct.

- [ ] **Step 3: Write minimal implementation or cleanup**

Fill any remaining glue gaps and keep tests focused on observable behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_nfo.py tests/test_organizer.py tests/test_engine.py -k "translate" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_nfo.py tests/test_organizer.py tests/test_engine.py
git commit -m "test: cover translate behavior across sort and nfo flows"
```

### Task 5: Final Verification And Docs

**Files:**
- Modify: `docs/USAGE.md`
- Optionally Modify: `report.md`
- Optionally Modify: `plan.md`

- [ ] **Step 1: Update user-facing docs**

Document:
- what `affect_sort_names` does
- provider install requirements
- the default safe behavior

- [ ] **Step 2: Run targeted verification**

Run:
- `./venv/bin/python -m pytest tests/test_config.py tests/test_translator.py tests/test_engine.py tests/test_organizer.py tests/test_nfo.py tests/test_cli.py -q`
- `./venv/bin/python -m ruff check javs tests`

Expected:
- all selected tests pass
- ruff passes cleanly

- [ ] **Step 3: Commit**

```bash
git add docs/USAGE.md report.md plan.md
git commit -m "docs: document translate scope and verification"
```
