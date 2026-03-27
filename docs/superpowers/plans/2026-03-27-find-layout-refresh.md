# Find Layout Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the default `javs find` output into a cleaner "hero + detail rows" layout with inline provenance.

**Architecture:** Keep the data pipeline unchanged and limit the work to CLI presentation. Replace the current multi-panel `find` renderer with one unified structured surface that displays provenance beside each value instead of in a separate block.

**Tech Stack:** Python, Typer, Rich, pytest

---

### Task 1: Lock The New CLI Output In Tests

**Files:**
- Modify: `tests/test_cli.py`

- [ ] Update the existing `find` renderer tests to assert the new layout shape.
- [ ] Add assertions for:
  - header-style title display
  - no `Field Provenance` section
  - inline provenance tags
  - full description rendering
  - omission of empty rows
- [ ] Run:

```bash
./venv/bin/python -m pytest tests/test_cli.py -q
```

- [ ] Confirm the updated tests fail before implementation.

### Task 2: Implement The New `find` Renderer

**Files:**
- Modify: `javs/cli.py`

- [ ] Replace the current multi-panel renderer with a unified layout.
- [ ] Add helpers for:
  - inline provenance formatting
  - URL shortening for display
  - aligned row rendering
- [ ] Keep:
  - full description output
  - omission of empty fields
  - current data values unchanged

- [ ] Run:

```bash
./venv/bin/python -m pytest tests/test_cli.py -q
```

- [ ] Confirm the renderer tests now pass.

### Task 3: Update User-Facing Docs And Verify Broadly

**Files:**
- Modify: `docs/USAGE.md`

- [ ] Update the `find` description so it matches the new layout.
- [ ] Run:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

- [ ] Confirm full verification passes before handoff.
