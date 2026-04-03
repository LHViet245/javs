# JavS Troubleshooting

This guide is organized by symptom. Start with the message or behavior you see, confirm the likely cause, and only then change the config or rerun a larger batch.

If you need the normal workflow, use [Getting Started](./getting-started.md). If you need full syntax, use [Commands](./commands.md). If you need config details, use [Configuration](./configuration.md).

## No Files Were Processed

### What It Usually Means

`sort` scanned the source path but did not find any files it could actually process. Common causes:

- the path is wrong
- the files do not have supported extensions
- the filenames do not contain recognizable IDs
- the files were filtered out by `match.minimum_file_size_mb` or `match.excluded_patterns`

### How To Confirm It

Check the exact command you ran and inspect a few filenames in the source folder. Then run:

```bash
./venv/bin/javs sort /path/to/input /path/to/library --preview
```

If the preview still reports no files, test one ID manually:

```bash
./venv/bin/javs find "ABP-420"
```

### How To Fix It

- rename files so the ID is in the filename itself
- confirm the extension is in `match.included_extensions`
- lower `match.minimum_file_size_mb` if it is filtering valid files
- review `match.excluded_patterns` for accidental matches
- point `sort` at the real source directory

### When To Move On

If `find` works for a known ID but `sort` still processes nothing, focus on filename matching rather than scraper troubleshooting.

## Some Files Were Skipped

### What It Usually Means

The batch found some files, but one or more were skipped because JavS could not complete the pipeline for those items.

Common causes:

- no ID could be extracted from the filename
- the movie returned no metadata from the enabled scrapers
- the aggregated result was missing one of the required fields in `sort.metadata.required_fields`

### How To Confirm It

Check the batch summary. Then test a skipped file by its ID with:

```bash
./venv/bin/javs find "THE-ID"
```

Also review these config areas:

- `match.mode`
- `sort.metadata.required_fields`
- `scrapers.enabled`

### How To Fix It

- clean up the filename and remove extra noise
- temporarily reduce the required field list only if you understand the trade-off
- enable a scraper that is more likely to provide the missing field
- rerun the batch later if the upstream source is temporarily unstable

### When To Move On

If the same file always skips and `find` also returns incomplete metadata, treat it as a source-data problem instead of a sort bug.

## Wrong ID Matched

### What It Usually Means

The filename matched a valid-looking ID, but not the one you intended.

This usually happens when:

- the filename contains several ID-like fragments
- the filename has too much unrelated text
- your naming scheme would work better with `match.mode: strict`

### How To Confirm It

Run a preview sort on the file:

```bash
./venv/bin/javs sort /path/to/input /path/to/library --preview
```

If the preview plan shows the wrong ID, the problem is the filename match, not the scraper result.

### How To Fix It

- rename the file into a cleaner form such as `ABP-420.mp4`
- try `match.mode: strict` if your library uses clear dashed IDs
- use `match.mode: custom` only if your whole library follows a stable custom naming scheme

### When To Move On

If a cleaned filename still matches incorrectly in `strict` mode, then it is worth designing a custom regex for your library.

## Javlibrary Blocked By Cloudflare

### What It Usually Means

Javlibrary is enabled, but Cloudflare blocked the request or your saved `cf_clearance` expired.

### How To Confirm It

You will usually see a warning that mentions Cloudflare and suggests the Javlibrary credential helper. You can validate the current saved credentials with:

```bash
./venv/bin/javs config javlibrary-test
```

### How To Fix It

Refresh the saved credentials:

```bash
./venv/bin/javs config javlibrary-cookie
./venv/bin/javs config javlibrary-test
```

That flow saves a fresh `cookie_cf_clearance` and uses the saved browser user agent if one already exists.

### When To Move On

If Javlibrary is optional for your workflow, disable it in `scrapers.enabled` and continue with `r18dev` and `dmm` while you troubleshoot access separately.

## Proxy Test Failed

### What It Usually Means

`./venv/bin/javs config proxy-test` could not complete a simple proxied request.

Possible reasons:

- `proxy.enabled` is `false`
- `proxy.url` is empty or malformed
- the proxy is unreachable
- authentication failed

### How To Confirm It

Run:

```bash
./venv/bin/javs config proxy-test
```

Read the exact message. JavS reports distinct failures such as:

- `Proxy is disabled in config`
- `Proxy URL is missing from config`
- `Proxy authentication failed`
- `Proxy unreachable`
- `Proxy test failed`

### How To Fix It

- set `proxy.enabled: true`
- use a full URL with a scheme such as `http://` or `socks5://`
- verify username and password if the proxy requires auth
- confirm the host and port work outside JavS

### When To Move On

If `proxy-test` passes but a scraper still fails, the basic proxy config/connectivity check has already passed. The next thing to check is scraper-specific routing such as `scrapers.use_proxy`.

## Translation Provider Unavailable

### What It Usually Means

Translation is enabled in `sort.metadata.nfo.translate`, but the selected provider is not installed or the DeepL configuration is invalid.

### How To Confirm It

Run a normal `find`, `sort`, or `update` command and watch for a warning about translation. JavS keeps running, but it records a warning when the provider is missing or the DeepL language code is unsupported.

### How To Fix It

Install the translation extras:

```bash
./venv/bin/pip install -e ".[translate]"
```

Then review:

- `sort.metadata.nfo.translate.module`
- `sort.metadata.nfo.translate.language`
- `sort.metadata.nfo.translate.deepl_api_key`

For DeepL, use a supported target code such as `en-us`, `ja`, `vi`, or `pt-br`.

### When To Move On

If you do not need translation immediately, disable it and finish the rest of your workflow first.

## Update Did Not Refresh What I Expected

### What It Usually Means

`update` refreshed metadata in place, but it did not change something you expected, usually because `update` is narrower than `sort`.

Key runtime limits:

- `update` does not move or rename the video
- existing artwork is not re-downloaded unless you use `--refresh-images` or `--force`
- an existing trailer is not re-downloaded unless you use `--refresh-trailer` or `--force`
- trailer refresh still depends on `sort.download.trailer_vid: true`

### How To Confirm It

Preview the run:

```bash
./venv/bin/javs update /path/to/library --recurse --preview
```

That preview points to the NFO path JavS plans to update.

### How To Fix It

- use `sort` instead if you actually want to rename or move media again
- add `--refresh-images` when you want artwork replaced
- add `--refresh-trailer` when you want the trailer replaced
- use `--force` when you want existing sidecars and downloads overwritten broadly

### When To Move On

If the NFO updated but the folder and video name did not change, that is expected behavior for `update`.

## Source Directory Was Not Removed

### What It Usually Means

The sort finished, but JavS left the original source directory in place.

This is normal unless all of these are true:

- you used `--cleanup-empty-source-dir` or set `sort.cleanup_empty_source_dir: true`
- the video move succeeded
- the direct source directory became empty

### How To Confirm It

Review the command you ran and the config value:

```bash
./venv/bin/javs config show
```

Look at `sort.cleanup_empty_source_dir`.

### How To Fix It

- enable cleanup in config or pass `--cleanup-empty-source-dir`
- make sure no leftover files remain in the source directory
- remember that JavS only tries to remove the direct source directory, not a chain of parent directories

### When To Move On

If you intentionally left cleanup disabled for a cautious first run, there is nothing to fix.
