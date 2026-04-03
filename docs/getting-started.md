# Getting Started with JavS

This guide is for new users who want the safest path from first install to a working sorted library. It assumes you want to test a small sample first, confirm the output, and only then scale up.

If you already know the workflow and just need command syntax, use [Commands](./commands.md). If you need to tune behavior, use [Configuration](./configuration.md). If something goes wrong, use [Troubleshooting](./troubleshooting.md).

## Who This Guide Is For

Use this guide if you:

- are setting up JavS for the first time
- want a low-risk trial run before sorting a larger library
- need a simple path that uses the default workflow

This guide is not the full manual. It shows one practical starter path that matches the current CLI.

## Before You Start

JavS works best when:

- your video filenames already contain recognizable IDs such as `ABP-420`, `SSIS-001`, or `259LUXU-123`
- you start with a small test folder instead of your whole library
- you treat sorting and updating as two separate jobs

Important runtime rules:

- JavS is filename-driven. It extracts IDs from the filename, not from the parent folder name.
- `sort` moves and renames files into a library structure.
- `update` refreshes sidecars in place and does not move the video again.

Good test filenames:

- `ABP-420.mp4`
- `SSIS-001 CD1.mkv`
- `DVMM-377A.mp4`
- `259LUXU-123.mp4`

Risky filenames:

- `video.mp4`
- `movie_file.mkv`
- `SGKI-079/video.mp4`

In the last example, rename the file itself before sorting.

## Installation

From the repository root:

```bash
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
./venv/bin/javs --help
```

If `--help` prints the command list, the CLI is installed correctly.

## Config Creation And Check

First check where JavS expects the config file:

```bash
./venv/bin/javs config path
```

The default path is usually:

```text
~/.javs/config.yaml
```

Create the file explicitly:

```bash
./venv/bin/javs config create
```

Then inspect the effective values:

```bash
./venv/bin/javs config show
```

Safe starter defaults for a first run:

- keep `match.mode: auto`
- keep `scrapers.enabled.r18dev: true`
- keep `scrapers.enabled.dmm: true`
- keep `scrapers.enabled.javlibrary: false` until you know you need it
- keep `proxy.enabled: false` unless you already know a source requires your proxy
- keep `sort.cleanup_empty_source_dir: false` for the first real sort

## First `find`

Before sorting files, test one known movie ID:

```bash
./venv/bin/javs find "ABP-420"
```

What success looks like:

- JavS prints a movie inspector with the title and key fields
- no `No results found` error appears
- you can see enough metadata to trust the current scraper setup

Useful variants:

```bash
./venv/bin/javs find "ABP-420" --json
./venv/bin/javs find "ABP-420" --nfo
./venv/bin/javs find "ABP-420" --scrapers dmm,r18dev
```

If `find` fails, stop there and use [Troubleshooting](./troubleshooting.md) before moving files.

## Preview Sort

Create a small test input folder with a few files you can afford to move. Then preview the sort:

```bash
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse --preview
```

What to look for:

- the preview plan shows the source file, detected ID, and target path
- the target folder names look reasonable
- multipart files look correct, such as `-pt1` and `-pt2`

Do not move to a real sort until the preview plan looks right.

## First Real Sort

Run the same command without `--preview`:

```bash
./venv/bin/javs sort /path/to/test-input /path/to/library --recurse
```

Keep the first real run small. A good first batch is a handful of files, not your entire collection.

If you need to point JavS at a non-default config file, add `--config /path/to/config.yaml`.

## Checking Output

After the sort finishes, open the destination folder and confirm the results. A typical result looks like:

```text
ABP-420 [Studio] - Movie Title (2024)/
  ABP-420.mp4
  ABP-420.nfo
  fanart.jpg
  folder.jpg
```

Check these items:

- the folder name matches your expectations
- the video filename still contains the correct ID
- the `.nfo` exists
- artwork exists if the related downloads are enabled
- matching subtitle files moved with the video if `sort.move_subtitles` is enabled

If something looks wrong, fix the filename or config before you scale up.

## First `update`

Use `update` later when the files are already sorted and you want fresher metadata without moving the video again:

```bash
./venv/bin/javs update /path/to/library --recurse
```

Use these only when you want existing sidecars re-downloaded:

```bash
./venv/bin/javs update /path/to/library --recurse --refresh-images
./venv/bin/javs update /path/to/library --recurse --refresh-trailer
```

Important behavior:

- `update` rewrites NFO sidecars in place when NFO creation is enabled
- `update` does not rename or relocate the video file
- existing images and trailers are not refreshed unless you ask for it or use `--force`

## Next Steps

Once the small test batch looks good:

1. Adjust your config in [Configuration](./configuration.md) if you need different naming, NFO behavior, proxy routing, or translation.
2. Use [Commands](./commands.md) as the day-to-day reference for `find`, `sort`, `update`, `config`, and `scrapers`.
3. Use [Troubleshooting](./troubleshooting.md) when a batch reports skipped files, Cloudflare issues, proxy failures, or update surprises.
