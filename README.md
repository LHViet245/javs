# JavS

JavS is a fast, async-native Python CLI for finding JAV metadata by ID, sorting files into a structured media library, generating sidecar files, and refreshing an existing library in place. Choose it when you want a local, scriptable workflow that stays filename-driven, makes scraper behavior explicit, and scales from one lookup to batch maintenance without turning the CLI into a one-off scraper script.

## Project Summary

JavS is built for repeatable library management. It searches enabled scrapers in parallel, normalizes metadata into typed models, writes `.nfo` and artwork alongside video files, and keeps sort and update behavior predictable through config-driven rules.

## Who JavS Is For

- End users who want to test one movie ID, then sort a small folder safely before scaling up.
- Power users who want explicit config, proxy control, Cloudflare helpers, and repeatable batch behavior.
- Contributors who need a clear CLI entrypoint, local verification commands, and a path to deeper project context.

## What JavS Does Well

- Finds metadata for a single ID with `find`.
- Sorts filename-driven libraries with `sort`.
- Refreshes already organized libraries in place with `update`.
- Merges results from multiple enabled scrapers instead of relying on one source.
- Supports config sync, CSV template setup, proxy testing, and Javlibrary credential helpers.
- Keeps the pipeline async-first and typed, which helps with speed and predictable behavior.

## What JavS Does Not Do

- It does not infer IDs from folder names alone; the ID needs to be present in the filename.
- It does not guarantee perfect metadata when source sites disagree or return incomplete data.
- It is not a general-purpose media manager for arbitrary video collections without recognizable IDs.
- It does not remove the need to review config choices before sorting a real library.

## 5-Minute Quick Start

Set up the local environment and confirm the CLI works before touching a real library:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
./venv/bin/javs --help
./venv/bin/javs find "ABP-420"
```

If `find` returns metadata, JavS is installed correctly and at least one enabled scraper is responding.

## First Safe Workflow

1. Test one known ID with `find`:

   ```bash
   ./venv/bin/javs find "ABP-420"
   ```

2. Preview a sort before moving anything:

   ```bash
   ./venv/bin/javs sort /path/to/test-input /path/to/library --recurse --preview
   ```

3. Run a real sort on a small folder only after the preview looks right:

   ```bash
   ./venv/bin/javs sort /path/to/test-input /path/to/library --recurse
   ```

4. Inspect the results in the destination folder and confirm the renamed video, `.nfo`, and artwork look correct.

5. Use `update` later when you want to refresh metadata in place without moving the video again:

   ```bash
   ./venv/bin/javs update /path/to/library --recurse
   ```

## Documentation Map by Role

These are the role-based docs that this landing page points to:

| Role | Start here |
| --- | --- |
| New user | [Getting Started](docs/getting-started.md) |
| Configuring behavior | [Configuration](docs/configuration.md) |
| Looking up commands | [Commands](docs/commands.md) |
| Troubleshooting problems | [Troubleshooting](docs/troubleshooting.md) |
| Contributing | [Contributor Guide](docs/contributor-guide.md) |

Legacy paths remain for continuity: `docs/USAGE.md` is the documentation index, and `docs/PLAYBOOK.md` is a slim compatibility page for older links and bookmarks.

## Feature Overview

- Async scraping across the enabled sources in your config.
- File-name-driven ID detection, including multipart naming patterns.
- `find`, `sort`, and `update` for lookup, organization, and in-place refreshes.
- `config` subcommands for showing, editing, syncing, and initializing local settings.
- `scrapers` for listing available scraper plugins.
- Proxy and Javlibrary support helpers for environments that need them.
- Optional translation support for metadata fields.
- Typed configuration and model handling with `pydantic`.

## Contributor and Verification Note

Use the repository virtual environment for installs, app commands, and tests. Before opening a PR or handing work off, run the relevant checks from the repo root:

```bash
./venv/bin/python -m pytest tests -q
./venv/bin/python -m ruff check javs tests
```

For a full local verification pass, you can also run `./scripts/verify_local.sh`.
