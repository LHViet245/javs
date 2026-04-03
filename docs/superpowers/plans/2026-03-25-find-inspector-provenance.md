# Find Inspector Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `javs find` into a richer metadata inspector that shows assets and per-field provenance for every traceable field without changing JSON, NFO, `sort`, or `update` behavior.

**Architecture:** Add one explicit provenance contract to `MovieData`, populate it centrally in aggregation and translation, then teach the `find` renderer to display that richer metadata in a sectioned Rich layout. Keep the change isolated to shared data contracts plus the display path used by `find`, so the rest of the CLI keeps existing behavior.

**Tech Stack:** Python 3.11, Pydantic v2, Typer, Rich, async engine pipeline, pytest, ruff

---

### Task 1: Add A General Field Provenance Contract

**Files:**
- Modify: `javs/models/movie.py`
- Test: `tests/test_models.py` or `tests/test_aggregator.py`

- [ ] **Step 1: Write the failing tests**

Add regression coverage proving:
- `MovieData` accepts a new `field_sources` mapping
- model copies preserve `field_sources`
- asset-specific source fields remain independent and still work

Example test shape:

```python
def test_movie_data_preserves_field_sources():
    data = MovieData(
        id="ABP-420",
        title="Example",
        field_sources={"title": "dmm", "cover_url": "r18dev"},
    )

    copied = data.model_copy(deep=True)

    assert copied.field_sources == {"title": "dmm", "cover_url": "r18dev"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_models.py tests/test_aggregator.py -k field_sources -q`
Expected: FAIL because `MovieData` does not define the field yet.

- [ ] **Step 3: Write minimal implementation**

Add `field_sources: dict[str, str] = Field(default_factory=dict)` to `MovieData` in `javs/models/movie.py`. Do not remove or rename:
- `source`
- `cover_source`
- `trailer_source`
- `screenshot_source`

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_models.py tests/test_aggregator.py -k field_sources -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/models/movie.py tests/test_models.py tests/test_aggregator.py
git commit -m "feat: add movie field provenance mapping"
```

### Task 2: Populate Provenance In Aggregation

**Files:**
- Modify: `javs/core/aggregator.py`
- Test: `tests/test_aggregator.py`

- [ ] **Step 1: Write the failing tests**

Add focused tests proving:
- single-source merge populates `field_sources` for traceable fields from `data.source`
- multi-source merge records the winning scraper for normal scalar fields like `title`, `description`, `studio`, `rating`
- asset fields still populate `cover_source`, `trailer_source`, and `screenshot_source`, and those same values appear in `field_sources`

Example cases:

```python
def test_merge_single_source_populates_field_sources():
    result = aggregator.merge([
        MovieData(
            id="ABP-420",
            title="Example",
            description="Plot",
            source="dmm",
        )
    ])
    assert result.field_sources["title"] == "dmm"
    assert result.field_sources["description"] == "dmm"
```

```python
def test_merge_multi_source_tracks_field_winner():
    result = aggregator.merge([dmm_data, r18_data])
    assert result.title == "Winner"
    assert result.field_sources["title"] == "dmm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_aggregator.py -k "field_sources or source_winner" -q`
Expected: FAIL because aggregator does not assign the new mapping yet.

- [ ] **Step 3: Write minimal implementation**

In `javs/core/aggregator.py`:
- initialize `merged.field_sources`
- whenever the winning value for a field is chosen, record `field_sources[field_name]`
- for single-source data, backfill provenance from `data.source` for traceable populated fields
- mirror asset provenance into both the existing `*_source` fields and `field_sources`

Keep provenance field-level only. Do not add per-item provenance for lists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_aggregator.py -k "field_sources or source_winner" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/core/aggregator.py tests/test_aggregator.py
git commit -m "feat: track field provenance during aggregation"
```

### Task 3: Let Translation Override Provenance Only When It Changes A Field

**Files:**
- Modify: `javs/services/translator.py`
- Possibly Modify: `javs/core/engine.py`
- Test: `tests/test_translator.py`
- Possibly Modify: `tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Add tests proving:
- when a translated field changes, its `field_sources` entry becomes the translation provider name
- untranslated fields keep their original scraper provenance
- if translation returns `None` or unchanged text, provenance is preserved

Example test shape:

```python
async def test_translate_movie_data_updates_field_source_for_changed_field(monkeypatch):
    data = MovieData(
        id="ABP-420",
        description="Original",
        field_sources={"description": "dmm", "title": "r18dev"},
    )
    config = TranslateConfig(enabled=True, module="deepl", fields=["description"])

    async def fake_translate_text(text, cfg):
        return "Translated"

    monkeypatch.setattr(translator_module, "_translate_text", fake_translate_text)

    result = await translator_module.translate_movie_data(data, config)

    assert result.field_sources["description"] == "deepl"
    assert result.field_sources["title"] == "r18dev"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_translator.py tests/test_engine.py -k "field_sources and translate" -q`
Expected: FAIL because translation currently mutates text without provenance updates.

- [ ] **Step 3: Write minimal implementation**

Update translation flow so it:
- copies incoming `field_sources`
- overwrites `field_sources[field_name]` with `config.module` only when the translated value is materially different
- leaves provenance untouched for unchanged or failed translations

Keep the current single-pass translation behavior intact.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_translator.py tests/test_engine.py -k "field_sources and translate" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/services/translator.py javs/core/engine.py tests/test_translator.py tests/test_engine.py
git commit -m "feat: preserve translation provenance per field"
```

### Task 4: Redesign The `find` Renderer Into An Inspector View

**Files:**
- Modify: `javs/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add CLI output tests covering:
- `find` renders section headers `Identity`, `Release`, `People`, `Content`, `Assets`, `Field Provenance`
- provenance entries appear for all available tracked fields
- asset rows show URLs and screenshot count when present
- empty optional rows are omitted

Use a `MovieData` fixture with rich metadata plus `field_sources`, for example:

```python
movie = MovieData(
    id="ABP-420",
    title="Translated Title",
    description="Translated Plot",
    studio="IdeaPocket",
    genres=["Drama", "Romance"],
    actresses=[Actress(name="Aoi")],
    cover_url="https://example.com/cover.jpg",
    trailer_url="https://example.com/trailer.mp4",
    screenshot_urls=["https://example.com/1.jpg"],
    source="dmm",
    field_sources={
        "title": "deepl",
        "description": "deepl",
        "studio": "dmm",
        "genres": "r18dev",
        "cover_url": "dmm",
        "trailer_url": "mgstageja",
        "screenshot_urls": "dmm",
    },
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_cli.py -k "find and provenance" -q`
Expected: FAIL because the current renderer uses one compact panel.

- [ ] **Step 3: Write minimal implementation**

Refactor `_display_movie_data()` in `javs/cli.py`:
- keep Rich-based rendering
- build the new sectioned inspector layout
- render provenance entries in a stable human-friendly order
- shorten displayed URLs only for presentation
- omit empty rows and empty sections where appropriate

Do not change:
- `--json`
- `--nfo`
- run diagnostics rendering

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_cli.py -k "find and provenance" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/cli.py tests/test_cli.py
git commit -m "feat: add provenance inspector view for find"
```

### Task 5: Add Engine-Level Compatibility Coverage For `find`

**Files:**
- Modify: `tests/test_engine.py`
- Possibly Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add compatibility tests proving:
- `find()` returns `MovieData` with `field_sources` intact after aggregation
- translated `find()` results preserve provenance updates from translation
- `find_one()` output path still works with open/close session lifecycle unchanged

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_engine.py -k "find and field_sources" -q`
Expected: FAIL until the engine path consistently carries provenance-rich models through.

- [ ] **Step 3: Write minimal implementation or cleanup**

If needed, add glue in `javs/core/engine.py` so the `find` path does not drop `field_sources` during aggregate/translate/display flow. Avoid behavior changes outside provenance propagation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_engine.py -k "find and field_sources" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add javs/core/engine.py tests/test_engine.py tests/test_cli.py
git commit -m "test: cover provenance through the find pipeline"
```

### Task 6: Final Verification And User-Facing Docs

**Files:**
- Modify: `docs/USAGE.md`
- Optionally Modify: `report.md`
- Optionally Modify: `plan.md`

- [ ] **Step 1: Update docs**

Document the improved `find` experience in `docs/USAGE.md`:
- that `find` now shows richer metadata sections
- that field provenance is shown when traceable
- that translation providers may become the provenance source for changed fields

- [ ] **Step 2: Run broad verification**

Run:
- `./venv/bin/python -m pytest tests -q`
- `./venv/bin/python -m ruff check javs tests`

Expected:
- all tests pass
- ruff passes cleanly

- [ ] **Step 3: Review git scope**

Run:
- `git status --short`
- `git diff --stat`

Expected:
- only intended files for the `find` inspector/provenance work are included

- [ ] **Step 4: Commit**

```bash
git add docs/USAGE.md report.md plan.md
git commit -m "docs: document find provenance inspector"
```
