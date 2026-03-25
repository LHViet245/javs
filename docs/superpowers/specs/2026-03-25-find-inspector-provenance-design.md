# Find Inspector Provenance Design

**Date:** 2026-03-25

## Goal

Make `javs find` feel like a rich metadata inspector by showing a clearer, more detailed terminal layout and exposing provenance for every metadata field that can be traced back to a scraper or translation provider.

## Problem

Today `find` renders a compact summary panel that is easy to scan, but it hides too much context for power users and debugging:
- asset URLs are either absent or too implicit
- users cannot tell which scraper won each field during aggregation
- translated fields do not clearly show that the final value came from a translation provider rather than the original scraper
- the current layout is useful, but it does not fully support metadata auditing or scraper quality comparisons

The runtime already knows some source information such as `source`, `cover_source`, `trailer_source`, and `screenshot_source`, but that information is not modeled consistently across all metadata fields and is not surfaced in a structured `find` view.

## User Experience

`javs find` should become a richer inspector-style screen with clear visual sections:
- `Identity`
- `Release`
- `People`
- `Content`
- `Assets`
- `Field Provenance`

This view should remain terminal-friendly:
- values should still be easy to scan quickly
- long URLs should render compactly without mutating the underlying data
- empty fields should be omitted instead of producing noisy placeholders

The `Field Provenance` section should list every field whose winning value can be traced. Users should be able to understand both:
- what the final value is
- where that value came from

## Provenance Model

Add a general provenance contract to `MovieData`:

```python
field_sources: dict[str, str]
```

Semantics:
- keys are canonical `MovieData` field names
- values are the scraper or provider name responsible for the final field value
- omit fields that cannot be traced confidently

Examples:
- `title -> dmm`
- `description -> deepl`
- `genres -> r18dev`
- `cover_url -> dmm`
- `screenshot_urls -> mgstageja`

This contract should complement, not immediately replace, the existing dedicated asset source fields:
- `source`
- `cover_source`
- `trailer_source`
- `screenshot_source`

For backward compatibility:
- those existing fields should keep working
- when asset provenance is known, it should also be reflected in `field_sources`

## Aggregation Behavior

Aggregation should be the primary place that assigns provenance.

When the aggregator chooses a winning value for a field:
- it should also set `field_sources[field_name]` to the winning scraper name

This applies to:
- single-source results
- merged multi-source results

Single-source results are important: even when no merge conflict exists, `find` should still show provenance for all traceable fields instead of leaving `field_sources` mostly empty.

For list or structured fields:
- provenance is tracked at the field level, not per-item
- for example, `genres` gets one source entry, not one per genre
- `actresses` gets one source entry for the final actress list

## Translation Behavior

Translation should be allowed to override provenance only for fields it actually changes.

Rules:
- if translation is disabled, provenance stays fully scraper-based
- if translation is enabled and a field is translated successfully, that field's provenance should move to the translation provider
- if translation fails, is skipped, or returns unchanged content, provenance should remain with the original scraper

Examples:
- original `description` from `dmm`, translated by `deepl` -> `description -> deepl`
- original `title` from `r18dev`, translation disabled -> `title -> r18dev`

This keeps the inspector honest: it reports the source of the final user-facing field value, not merely the source of the pre-translation text.

## `find` Layout

The default `find` renderer should keep using Rich, but move from one dense panel to a structured inspector layout.

### Identity

Fields:
- `ID`
- `Title`
- `Original Title` when it differs or is separately available
- `Primary Source`

### Release

Fields:
- `Studio`
- `Label`
- `Series`
- `Release Date`
- `Runtime`
- `Rating`

### People

Fields:
- `Actresses`
- `Director`

### Content

Fields:
- `Genres`
- `Description`

### Assets

Fields:
- `Cover URL`
- `Trailer URL`
- `Screenshot Count`
- optional compact source summary for asset groups when useful

### Field Provenance

Fields:
- every entry in `field_sources`, rendered in a stable human-friendly order
- fields not covered by the preferred order may appear afterward in sorted order

Preferred ordering should prioritize the fields users care about first, for example:
- `title`
- `description`
- `studio`
- `release_date`
- `runtime`
- `rating`
- `genres`
- `actresses`
- `director`
- `cover_url`
- `trailer_url`
- `screenshot_urls`

## Scope Boundaries

This change is intentionally scoped to the `find` experience and the provenance data it needs.

Non-goals:
- no JSON output redesign
- no NFO output redesign
- no changes to `sort` or `update` behavior beyond carrying richer provenance data through shared models
- no per-item provenance inside list fields
- no scraper scorecard or side-by-side per-scraper comparison view

## Error Handling

The inspector must degrade gracefully:
- if `field_sources` is partially populated, `find` still renders normally
- if some fields are missing entirely, the corresponding rows are omitted
- if URLs are extremely long, the display may shorten them without mutating the actual model
- provenance display must never be required for a successful `find`

## Testing

Minimum regression coverage:
- aggregator tests prove `field_sources` is populated for single-source and multi-source results
- translation tests prove translated fields can reassign provenance to the translation provider
- CLI tests prove `find` renders the new sections and includes provenance for traceable fields
- compatibility tests prove existing asset-specific source fields still behave as before

## Risks

The main risk is widening the data contract too casually. Provenance should be added as one explicit field with clear semantics, not as ad hoc per-view metadata assembled in CLI code.

The second risk is overloading the `find` screen with noise. The layout should be richer than today, but still omit empty rows and prefer readability over dumping every raw field indiscriminately.

## Success Criteria

This work is successful when:
- `javs find` visibly feels richer and more informative than the current single-panel output
- users can tell which scraper or provider supplied every traceable field
- translated fields clearly show translation-provider provenance when applicable
- the implementation preserves current `sort`, `update`, JSON, and NFO behavior
