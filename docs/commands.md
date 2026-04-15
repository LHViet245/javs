# JavS Command Reference

This page is the command lookup for everyday use. It focuses on what each command is for, when to use it, the syntax that actually exists in the CLI, and the mistakes that most often waste time.

If you want a guided first run, start with [Getting Started](./getting-started.md). If you need config advice, use [Configuration](./configuration.md).

## Global Usage Pattern

Use the repository virtual environment:

```bash
./venv/bin/javs [COMMAND] [ARGS] [OPTIONS]
```

Examples:

```bash
./venv/bin/javs --help
./venv/bin/javs --version
./venv/bin/javs sort /path/to/input /path/to/library --recurse
```

Notes:

- `find`, `sort`, `update`, and `config` accept `--config /path/to/config.yaml`
- `scrapers` has no config-specific options
- `--preview` is available on `sort` and `update` only

## `find`

### Purpose

Look up metadata for one movie ID without moving files.

### When To Use It

Use `find` when you want to:

- confirm that your current scraper setup works
- compare results for one movie before sorting a batch
- inspect JSON or NFO output for a known ID

### Syntax

```bash
./venv/bin/javs find [OPTIONS] MOVIE_ID
```

### Examples

```bash
./venv/bin/javs find "ABP-420"
./venv/bin/javs find "ABP-420" --json
./venv/bin/javs find "ABP-420" --nfo
./venv/bin/javs find "ABP-420" --scrapers dmm,r18dev
./venv/bin/javs find "ABP-420" --config /path/to/config.yaml
```

### Expected Outcome

- terminal inspector output by default
- JSON output with `--json`
- NFO XML with `--nfo`
- exit code `1` if no result is found
- warning hints if a scraper hits proxy or Cloudflare issues

### Common Mistakes

- passing a filename instead of a movie ID
- assuming `find` tests filename matching; it does not
- enabling Javlibrary and ignoring Cloudflare warnings instead of validating credentials

## `sort`

### Purpose

Scan video files, extract IDs from filenames, scrape metadata, generate sidecars, and move files into the destination library.

### When To Use It

Use `sort` when you want to organize unsorted files into your library structure.

### Syntax

```bash
./venv/bin/javs sort [OPTIONS] SOURCE DEST
```

Options:

- `--recurse`, `-r`: scan subdirectories
- `--force`, `-f`: overwrite existing files
- `--preview`, `-p`: show what would happen without moving files
- `--cleanup-empty-source-dir` or `--no-cleanup-empty-source-dir`: override the config setting for this run
- `--config`, `-c`: use a specific config file

### Examples

```bash
./venv/bin/javs sort /path/to/input /path/to/library --preview
./venv/bin/javs sort /path/to/input /path/to/library --recurse --preview
./venv/bin/javs sort /path/to/input /path/to/library --recurse
./venv/bin/javs sort /path/to/input /path/to/library --recurse --force
./venv/bin/javs sort /path/to/input /path/to/library --recurse --cleanup-empty-source-dir
```

### Expected Outcome

- a result table when files were processed
- `No files were processed.` when the scan found nothing usable
- a preview plan table when `--preview` is used
- a summary with scanned, processed, skipped, failed, and warning counts

### Common Mistakes

- expecting JavS to detect IDs from folder names instead of filenames
- skipping preview on a new naming template
- pointing `SOURCE` at the wrong folder and assuming the scraper failed
- assuming `--cleanup-empty-source-dir` removes nested folders; it only tries to remove the direct source directory when it is empty

## `update`

### Purpose

Refresh metadata sidecars for an already-sorted library without moving the video files.

### When To Use It

Use `update` when your library is already in place and you want fresher metadata, NFO content, or optional re-downloads.

### Syntax

```bash
./venv/bin/javs update [OPTIONS] SOURCE
```

Options:

- `--recurse`, `-r`: scan subdirectories
- `--scrapers`, `-s`: use only the named scrapers
- `--force`, `-f`: overwrite sidecars and downloads
- `--refresh-images`: re-download existing cover, poster, actress, and screenshot images
- `--refresh-trailer`: re-download an existing trailer file when a trailer URL is available
- `--preview`, `-p`: show what would happen without writing files
- `--config`, `-c`: use a specific config file

### Examples

```bash
./venv/bin/javs update /path/to/library --recurse
./venv/bin/javs update /path/to/library --recurse --preview
./venv/bin/javs update /path/to/library --recurse --refresh-images
./venv/bin/javs update /path/to/library --recurse --refresh-trailer
./venv/bin/javs update /path/to/library --recurse --scrapers dmm,r18dev
```

### Expected Outcome

- a result table when files were updated
- `No files were updated.` when the scan found nothing usable
- a preview plan table that points to the NFO path in preview mode
- a summary with processed, skipped, failed, and warning counts

### Common Mistakes

- expecting `update` to rename or move the video file
- assuming existing artwork will refresh without `--refresh-images` or `--force`
- expecting trailer downloads when `sort.download.trailer_vid` is disabled in config

## `config`

### Purpose

Create, inspect, edit, and validate JavS configuration.

### When To Use It

Use `config` when you need to:

- create or locate the config file
- inspect effective settings
- sync in new defaults after an upgrade
- set up CSV templates
- validate proxy or Javlibrary credentials
- save validated settings changes and record a settings audit job

### Syntax

```bash
./venv/bin/javs config [ACTION] [--config PATH]
```

Supported actions:

- `show`
- `save`
- `edit`
- `create`
- `path`
- `sync`
- `csv-paths`
- `init-csv`
- `javlibrary-cookie`
- `javlibrary-test`
- `proxy-test`

### Examples

```bash
./venv/bin/javs config path
./venv/bin/javs config create
./venv/bin/javs config show
./venv/bin/javs config save --changes '{"proxy": {"enabled": true, "url": "http://127.0.0.1:8888"}}'
./venv/bin/javs config edit
./venv/bin/javs config sync
./venv/bin/javs config init-csv
./venv/bin/javs config csv-paths
./venv/bin/javs config proxy-test
./venv/bin/javs config javlibrary-cookie
./venv/bin/javs config javlibrary-test
```

### Expected Outcome

- `path` prints the config path
- `create` writes a default config file
- `show` prints masked JSON
- `save` writes the YAML config back to disk after validation and records a `save_settings` job plus a settings audit row
- `edit` opens the file in `$EDITOR` or `$VISUAL`, defaulting to `nano`
- `sync` merges your local config with the packaged template
- `init-csv` creates local CSV templates and records their paths in config
- `proxy-test` returns success or a readable failure reason
- `javlibrary-test` validates the saved Cloudflare credentials

### Common Mistakes

- assuming `show` proves a config file already exists; it can also display built-in defaults
- assuming `save` can change `database.path`; that path remains managed through the YAML config and shared application rules
- editing YAML by hand but never running `sync` after schema changes
- running `proxy-test` while `proxy.enabled` is still `false`
- setting Javlibrary fields manually without validating them

## `scrapers`

### Purpose

List the scraper plugins currently registered in the CLI.

### When To Use It

Use `scrapers` when you want to confirm the built-in scraper names before setting `scrapers.enabled`, `scrapers.use_proxy`, or `--scrapers`.

### Syntax

```bash
./venv/bin/javs scrapers
```

### Examples

```bash
./venv/bin/javs scrapers
```

### Expected Outcome

- a table of registered scraper names
- status shown as `registered`

### Common Mistakes

- assuming `scrapers` shows which sources are enabled in your config; it lists registered plugins, not your current config state
- using scraper names in `--scrapers` that do not appear in this list

## History And Realtime Backend Surface

JavS now exposes a small backend read surface for history and live job updates. It is intended for future dashboard and automation clients, not as a completed dashboard product.

### `GET /jobs`

Purpose:

- list recent jobs from the stored history database
- support future UI and API clients that need cursor-based browsing

Query parameters:

- `limit`
- `cursor`
- `kind`
- `status`
- `origin`
- `q`

Notes:

- default `limit` is `20`
- maximum `limit` is `100`
- results are ordered newest-first by `created_at DESC, id DESC`
- the cursor is opaque and should be reused with the same filter and search parameters that produced it
- search matches `job_id`, `job_items.movie_id`, `job_items.source_path`, and `job_items.dest_path`
- list items include progress counters such as `processed`, `skipped`, `failed`, and `warnings`

### `GET /jobs/{id}`

Purpose:

- load one stored job with its detail payload
- support future detail or side-panel views

Response includes:

- the job summary row
- result payload
- job items
- stored events in timeline order
- settings audit data when the job is `save_settings`

### `GET /settings`

Purpose:

- read the active settings view

Important:

- YAML remains the editable source of truth for settings
- SQLite stores jobs, events, and settings audit history, but it is not the live settings source

### Realtime Feeds

JavS exposes two realtime transports over the same logical job event model:

- `GET /events/stream` for SSE
- `/ws/jobs` for WebSocket subscriptions

Subscription notes:

- `{"action":"subscribe"}`
- `{"action":"subscribe","job_id":"..."}`
- omit `job_id` to subscribe to the global stream
- provide `job_id` to subscribe to one job
- both transports publish the same live event content
