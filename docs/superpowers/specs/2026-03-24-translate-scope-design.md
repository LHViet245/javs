# Translate Scope Design

**Date:** 2026-03-24

## Goal

Make metadata translation predictable for end users by letting them choose whether translated text should also affect sort naming, while keeping translation work to a single pass per movie.

## Problem

Today translation is configured under `sort.metadata.nfo.translate`, but the engine mutates `MovieData` before organizer and NFO generation both consume it. That means translating `title` can change folder and file names even though the config looks NFO-scoped.

This creates two issues:
- Users who only want translated NFO text can get unexpected renamed folders/files.
- The pipeline intent is unclear because config placement and runtime behavior do not match.

## User Decision

Add a direct boolean:

```yaml
sort:
  metadata:
    nfo:
      translate:
        enabled: false
        affect_sort_names: false
```

Semantics:
- `affect_sort_names: false`
  - `find` may still display translated text.
  - `sort` and `update` must keep original metadata for path building.
  - NFO output should use translated metadata.
- `affect_sort_names: true`
  - Existing broad behavior is preserved.
  - Translated metadata may affect naming and NFO output.

## Architecture

Translation should happen at most once per movie lookup result. The pipeline should produce one translated copy and then choose where to use it:
- original `MovieData` for naming when `affect_sort_names` is `false`
- translated `MovieData` for NFO generation
- translated `MovieData` for all downstream uses when `affect_sort_names` is `true`

To support that cleanly:
- `JavsEngine.find()` should remain the shared place where aggregation and translation happen.
- Batch flows (`sort_path`, `update_path`) should choose the original vs translated object explicitly.
- Organizer/NFO writing should be able to receive a dedicated NFO data object when naming and NFO content differ.

## Runtime Behavior

### `find`

`find` is a display-oriented command, so when translation is enabled it should show translated values regardless of `affect_sort_names`.

### `sort`

When translation is enabled:
- if `affect_sort_names` is `false`, folder/file/NFO filenames use original metadata, while NFO body uses translated metadata
- if `affect_sort_names` is `true`, both naming and NFO body use translated metadata

### `update`

When translation is enabled:
- if `affect_sort_names` is `false`, existing library paths remain untouched and refreshed NFO content uses translated metadata
- if `affect_sort_names` is `true`, behavior stays aligned with the broad translated metadata path

## Preflight / UX

Translation providers are optional dependencies. When translation is enabled but the configured provider is unavailable:
- the app should warn clearly
- the pipeline should not crash
- users should get a concrete install hint

## Testing

Minimum regression coverage:
- config model/default config include `affect_sort_names`
- engine/translation tests prove `find` still returns translated metadata
- organizer/NFO integration tests prove `sort` and `update` can keep original naming while writing translated NFO content
- warning/preflight tests prove missing providers are surfaced clearly

## Non-Goals

- No translation result caching in this change
- No new translation providers
- No attempt to translate non-string structured metadata
