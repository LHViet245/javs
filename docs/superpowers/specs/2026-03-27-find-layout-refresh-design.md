# Find Layout Refresh Design

**Date:** 2026-03-27

## Goal

Redesign the default `javs find` terminal output so it feels cleaner, more aligned, and easier to scan while still showing the same metadata richness and inline provenance.

## Problem

The current inspector-style `find` layout is informative, but it feels visually busy:
- too many separate panels
- provenance in its own section creates extra noise
- short metadata fields are spread across too many boxes
- the terminal spends more space on framing than on values

Users still want the same information:
- translated title and original title
- release metadata
- people metadata
- assets
- full description
- provenance for every traceable field

The issue is presentation density, not missing data.

## User Experience

The new `find` output should follow a "hero + detail rows" layout:

- a compact header with:
  - `ID`
  - translated or final `Title`
  - `Original Title` when present
  - `Primary Source`
- a dense, aligned metadata body
- inline provenance tags shown directly beside each field value
- a full, non-truncated description block at the bottom

This should keep provenance visible without forcing users to jump to a separate section.

## Layout

### Header

Top area should prioritize identity:
- `ID`
- `Title`
- `Original Title`
- `Primary Source`

The title should remain visually dominant.

### Detail Rows

Short fields should be shown in a denser two-column layout when space allows:
- `Studio`
- `Label`
- `Series`
- `Release Date`
- `Runtime`
- `Rating`
- `Director`
- `Actresses`

Longer fields should use full-width rows:
- `Genres`
- `Cover URL`
- `Trailer URL`
- `Screenshot Count`

### Description

`Description` should render in full and should no longer be truncated in the default `find` view.

### Provenance

Provenance should be rendered inline as a muted source tag beside the displayed value:

- `Das [dmm]`
- `2026-03-24 [dmm]`
- `Translated title [deepl]`

There should no longer be a dedicated `Field Provenance` block in the default terminal layout.

## Formatting Rules

- omit empty rows
- shorten very long URLs for display only
- keep labels visually consistent and compact
- prefer one main panel or one unified structured surface over many separate panels
- keep the layout terminal-friendly on standard-width shells

## Scope

In scope:
- `_display_movie_data()` layout only
- CLI rendering tests
- user-facing docs for `find`

Out of scope:
- provenance data model changes
- aggregation logic changes
- translation pipeline changes
- JSON output changes
- NFO output changes

## Success Criteria

This redesign is successful when:
- `find` looks cleaner and less noisy than the current multi-panel inspector
- all important metadata remains visible
- provenance is still visible for traceable fields
- description shows in full
- tests confirm the new layout behavior
