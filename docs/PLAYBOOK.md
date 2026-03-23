# JavS Everyday User Playbook

This guide is for everyday end users who want a practical, low-risk way to use JavS successfully.

JavS works best as a repeatable workflow:

1. Test one movie ID with `find`
2. Sort a small folder
3. Check the result
4. Scale up to bigger batches
5. Use `update` later to refresh metadata

## What JavS Is Best At

JavS is an async CLI for:

- detecting movie IDs from video filenames
- scraping metadata from enabled sources
- generating `.nfo` files
- downloading sidecar assets
- sorting files into a cleaner library structure
- refreshing metadata later without moving the video again

It is strongest when your filenames already contain recognizable IDs.

## First-Time Setup

Use the repo virtual environment for everything:

```bash
./venv/bin/pip install -e ".[dev]"
./venv/bin/javs --help
./venv/bin/javs config path
./venv/bin/javs config create
```

The default config path is usually:

```text
~/.javs/config.yaml
```

## Safe Starter Configuration

For everyday users, start simple.

Recommended defaults:

- `match.mode: auto`
- `scrapers.enabled.r18dev: true`
- `scrapers.enabled.dmm: true`
- `scrapers.enabled.javlibrary: false`
- `scrapers.enabled.javlibraryja: false`
- `scrapers.enabled.javlibraryzh: false`
- `scrapers.enabled.mgstageja: false`
- `proxy.enabled: false`

Why this setup:

- `auto` matching handles the widest range of common filenames
- `r18dev` and `dmm` are enough for many normal cases
- `javlibrary` is useful, but often becomes the first source to fail under Cloudflare
- proxy support is best added only when you know you need it

To inspect your current config:

```bash
./venv/bin/javs config show
```

## Filename Rules Before Sorting

JavS is filename-driven, not folder-name-driven.

Good filename examples:

- `ABP-420.mp4`
- `SSIS-001 CD1.mkv`
- `SSIS-001 CD2.mkv`
- `DVMM-377A.mp4`
- `DVMM-377B.mp4`
- `259LUXU-123.mp4`
- `RCTD-717_uncensored.mp4`
- `IPX001.mp4`

Bad or risky examples:

- `video.mp4`
- `random_movie.mp4`
- `SGKI-079/video.mp4`

The last example is important: if the ID is only in the folder name and not in the file name, JavS will usually skip it.

Recommended fix:

- rename `SGKI-079/video.mp4` to `SGKI-079/SGKI-079.mp4`

## What `auto` Matching Usually Handles Well

In normal use, `match.mode: auto` is the safest starting point.

It usually handles:

- standard IDs like `ABP-420`
- compact IDs like `IPX001`
- multipart names like `CD1`, `CD2`, `pt2`
- letter parts like `A`, `B`
- numeric-prefix IDs like `259LUXU-123`
- filenames with extra tags around the ID

Examples:

- `[Thz.la]ABP-420.1080p.mp4`
- `SSIS-001 CD1.mkv`
- `START-539 pt2.mp4`
- `DVMM-377A.mp4`

## What to Avoid at First

Avoid these until your basic workflow is stable:

- `match.mode: custom`
- enabling every scraper at once
- sorting a huge library on your first run
- relying on folder names instead of file names

`custom` mode is powerful, but it is easier to misconfigure and can reduce match quality if your regex is not designed carefully for your own library.

## Step 1: Test a Single Movie ID

Before sorting a whole folder, test one or two known IDs:

```bash
./venv/bin/javs find "ABP-420"
./venv/bin/javs find "SSIS-001"
./venv/bin/javs find "259LUXU-123"
```

If you want machine-readable output:

```bash
./venv/bin/javs find "ABP-420" --json
```

If `find` works, your scraper setup is probably good enough to move on.

If `find` does not work:

- try another ID
- try again later
- check whether the source site is blocked, rate-limited, or temporarily unstable
- keep `javlibrary` disabled until the basic flow works

## Step 2: Preview a Small Sort

Start with a small test folder.

Preview first:

```bash
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse --preview
```

Then run the real sort:

```bash
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse
```

Why preview first:

- you can catch bad filenames before files move
- you can confirm that the destination layout looks right
- it is the safest way to validate your config

## What a Good Sorted Result Looks Like

Single-part example:

```text
ABP-420 [Studio] - Movie Title (2024)/
  ABP-420.mp4
  ABP-420.nfo
  folder.jpg
  fanart.jpg
```

Multipart example:

```text
SSIS-001 [Studio] - Movie Title (2024)/
  SSIS-001-pt1.mkv
  SSIS-001-pt2.mkv
  SSIS-001.nfo
```

If a matching subtitle exists, JavS may move it with the video:

```text
ABP-420 [Studio] - Movie Title (2024)/
  ABP-420.mp4
  ABP-420.nfo
  ABP-420.srt
```

## What Happens During Sort

In normal operation, JavS will:

1. scan files
2. extract IDs from filenames
3. scrape metadata from enabled sources
4. merge metadata
5. generate `.nfo`
6. download images if enabled
7. move and rename the video
8. move matching subtitle files

## Common First-Run Mistakes

### No files were processed

Likely causes:

- filenames do not contain recognizable IDs
- file extensions are unsupported
- you pointed to the wrong folder

Fix:

- rename files so the ID is in the filename
- test one file first with `find`

### Some files were skipped

Likely causes:

- no ID could be extracted
- metadata came back incomplete
- the source sites had temporary issues

Fix:

- clean up the filename
- test the movie ID manually with `find`
- retry later if a live source is unstable

### Wrong ID matched

Likely causes:

- messy filenames
- unusual FC2-style naming
- too much extra text around the ID

Fix:

- rename the file into a cleaner form like `ABP-420.mp4`
- keep `match.mode: auto`
- only move to custom regex if your whole library follows a known consistent pattern

### Duplicate files stayed behind in the source folder

This is a real-world situation JavS handles conservatively.

If multiple files collapse to the same destination name, JavS will not overwrite unless you use `--force`.

Typical examples:

- `ABP-420.mp4`
- `ABP-420-C.mp4`
- `ABP-420 subtitle-C.mp4`
- `[Thz.la]ABP-420.1080p.mp4`

These can all resolve to the same movie ID.

What to do:

- review leftover files manually
- keep the version you actually want
- rename alternate versions before re-running if needed

## Step 3: Scale Up to Bigger Batches

Once a small folder works, scale up gradually:

```bash
./venv/bin/javs sort /path/to/unsorted /path/to/library --recurse
```

Good habit:

- sort one studio folder or one day’s downloads first
- avoid your entire backlog on the first large run

## Step 4: Refresh an Existing Library

Use `update` after your library is already sorted and you want fresher metadata.

Basic refresh:

```bash
./venv/bin/javs update /path/to/library --recurse
```

Refresh images and trailer too:

```bash
./venv/bin/javs update /path/to/library --recurse --refresh-images --refresh-trailer
```

What `update` is for:

- rewriting `.nfo`
- refreshing metadata sidecars
- refreshing images when requested
- keeping video files in place

Use `update` when:

- the movie folder already exists
- you want better metadata later
- you do not want another move/rename pass

## When to Enable Javlibrary

Enable `javlibrary` only when:

- you need it for missing metadata or ratings
- your basic `r18dev` and `dmm` flow already works
- you are ready to handle Cloudflare friction

Helpful commands:

```bash
./venv/bin/javs config javlibrary-cookie
./venv/bin/javs config javlibrary-test
```

If Javlibrary is blocked, common symptoms are:

- search works sometimes and then stops
- credentials expire
- Cloudflare challenge interrupts scraping

## When You Might Need a Proxy

Proxy is not mandatory for every user, but it can help when:

- a source is geo-restricted
- a source behaves differently from your region
- one scraper consistently fails while others still work

Only enable proxy after a simple no-proxy setup has already been tested.

## Recommended Everyday Routine

Use this as your default operating pattern:

```bash
./venv/bin/javs find "ABP-420"
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse --preview
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse
./venv/bin/javs update /path/to/library --recurse
```

## Quick Do and Don't List

Do:

- keep `match.mode: auto`
- test one ID with `find` first
- use `--preview` on first sorts
- clean up filenames before batch sorting
- sort small batches before large ones
- use `update` for already-sorted libraries

Do not:

- rely on folder names instead of file names
- jump into `custom` regex mode immediately
- enable every scraper on day one
- assume every live scraping failure is a JavS bug
- mass-sort a large library before validating a small sample

## Practical Examples of Good Input

Good:

```text
ABP-420.mp4
IPX001.mp4
SSIS-001 CD1.mkv
SSIS-001 CD2.mkv
DVMM-377A.mp4
DVMM-377B.mp4
259LUXU-123.mp4
RCTD-717_uncensored.mp4
```

Risky:

```text
video.mp4
random_movie.mp4
SGKI-079/video.mp4
```

## If You Want the Safest Possible Start

1. Create config
2. Keep only `r18dev` and `dmm`
3. Test `find` with one known ID
4. Sort one small folder with `--preview`
5. Run the real sort
6. Check the output folder manually
7. Only then process larger batches

That approach prevents most painful mistakes.
