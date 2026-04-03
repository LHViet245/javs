# JavS Configuration Guide

This guide explains the config keys you are most likely to change in real use. It stays focused on practical choices: what a setting controls, a safe default, when to change it, and the mistakes that cause the most confusion.

If you are brand new, start with [Getting Started](./getting-started.md). If you only need command syntax, use [Commands](./commands.md).

## Config File Location

Check the active config path with:

```bash
./venv/bin/javs config path
```

By default, JavS uses:

```text
~/.javs/config.yaml
```

Create the file explicitly with:

```bash
./venv/bin/javs config create
```

Useful facts:

- `./venv/bin/javs config show` prints the effective config and masks sensitive values.
- `./venv/bin/javs config edit` creates the file first if it does not exist, then opens it in your editor.
- Most CLI commands also accept `--config /path/to/config.yaml` when you want a non-default file.

## Safe Starter Defaults

For a low-risk first setup, keep the config close to the packaged defaults:

```yaml
match:
  mode: auto

scrapers:
  enabled:
    r18dev: true
    dmm: true
    javlibrary: false
    javlibraryja: false
    javlibraryzh: false
    mgstageja: false

proxy:
  enabled: false

sort:
  cleanup_empty_source_dir: false
  download:
    thumb_img: true
    poster_img: true
    actress_img: false
    screenshot_img: false
    trailer_vid: false
```

Why these defaults are safe:

- `auto` matching covers the widest range of common filenames.
- `r18dev` and `dmm` are enough for many normal batches.
- Javlibrary is useful, but it is also the source most likely to need Cloudflare recovery.
- Leaving proxy and aggressive downloads off reduces the number of moving parts.
- Keeping source directory cleanup off makes first-run review easier.

The shorter version for first-run use is in [Getting Started](./getting-started.md). This section is the fuller reference.

## File Locations

The `locations` block mixes active path overrides with two schema fields that are not currently used by the built-in CLI/runtime:

```yaml
locations:
  input: ""
  output: ""
  thumb_csv: ""
  genre_csv: ""
  log: ""
```

What it controls:

- `thumb_csv` and `genre_csv` point to your override CSV files
- `log` sets a custom log file path

Current runtime truth:

- `locations.input` and `locations.output` exist in the schema, but the built-in `find`, `sort`, and `update` commands do not currently read them
- `sort` still requires explicit `SOURCE DEST` arguments on the command line
- `thumb_csv`, `genre_csv`, and `log` are the path keys in this block that have clear current runtime effect

Recommended default:

- leave `thumb_csv`, `genre_csv`, and `log` blank until you have a reason to pin them
- treat `input` and `output` as reserved/schema-only fields unless you have your own external tooling that reads them

When to change it:

- you want CSV templates in a non-default location
- you want logs written to a specific file
- you have your own wrapper scripts or notes that depend on fixed paths outside the built-in CLI behavior

Common mistakes:

- assuming `locations.input` or `locations.output` changes built-in CLI source or destination behavior
- pointing `thumb_csv` or `genre_csv` at files that do not exist yet

## Matching Modes

Matching controls how JavS extracts IDs from filenames:

```yaml
match:
  mode: auto
  minimum_file_size_mb: 0
  included_extensions:
    - .mp4
    - .mkv
  excluded_patterns:
    - "^.*-trailer*"
    - "^.*-5\\."
  regex_enabled: false
  regex:
    pattern: "([a-zA-Z|tT28]+-\\d+[zZ]?[eE]?)(?:-pt)?(\\d{1,2})?"
    id_match_group: 1
    part_match_group: 2
```

What it controls:

- `mode: auto` uses the built-in flexible patterns
- `mode: strict` requires clearer ID boundaries
- `mode: custom` uses your `match.regex` pattern
- `minimum_file_size_mb` filters out small files
- `included_extensions` defines which video files are scanned
- `excluded_patterns` skips matching filenames by regex

Recommended default:

- keep `match.mode: auto`

When to change it:

- use `strict` if `auto` is matching the wrong ID in your naming scheme
- use `custom` only when your whole library follows a consistent custom pattern
- raise `minimum_file_size_mb` if you keep picking up tiny samples or clips

Common mistakes:

- expecting JavS to read the parent folder name instead of the filename
- switching to `custom` too early and reducing match quality
- forgetting that `excluded_patterns` can silently remove files from the scan

Note:

- `regex_enabled` is still present for legacy compatibility, but new config should rely on `match.mode`.

## Scraper Enablement And Priorities

The `scrapers` and `sort.metadata.priority` blocks solve different problems.

Enable or disable sources here:

```yaml
scrapers:
  enabled:
    r18dev: true
    dmm: true
    javlibrary: false
    javlibraryja: false
    javlibraryzh: false
    mgstageja: false
  use_proxy:
    r18dev: false
    dmm: true
    javlibrary: false
    javlibraryja: false
    javlibraryzh: false
    mgstageja: true
```

Choose which scraper wins per field here:

```yaml
sort:
  metadata:
    priority:
      title:
        - r18dev
        - javlibrary
      description:
        - dmm
        - r18dev
        - mgstageja
      cover_url:
        - r18dev
        - javlibrary
        - dmm
```

What it controls:

- `scrapers.enabled` decides which scrapers are queried at all
- `scrapers.use_proxy` decides which sources use the configured proxy
- `priority` decides which scraper wins when multiple sources return the same field

Recommended default:

- enable only the sources you trust and can reach reliably
- change `priority` only after you see a repeatable quality problem

When to change it:

- a source is blocked or unstable in your environment
- you prefer a different source for descriptions, titles, covers, or release dates
- you want DMM or MGStage to use a proxy while other sources stay direct

Common mistakes:

- enabling many sources before validating the basic workflow
- assuming `scrapers.use_proxy` matters when `proxy.enabled` is still `false`
- changing field priorities before you know which source is actually wrong

## Sort And Naming

The `sort` block controls how files and folders are named and whether JavS moves related assets:

```yaml
sort:
  move_to_folder: true
  rename_file: true
  move_subtitles: true
  cleanup_empty_source_dir: false
  format:
    file: "{id}"
    folder: "{id} [{studio}] - {title} ({year})"
    poster_img:
      - folder
    thumb_img: fanart
    trailer_vid: "{id}-trailer"
    nfo: "{id}"
    screenshot_img: fanart
    screenshot_padding: 1
    screenshot_folder: extrafanart
    actress_img_folder: ".actors"
    delimiter: ", "
    max_title_length: 100
```

What it controls:

- whether the video is moved into its own folder
- whether the video filename is renamed
- whether matching subtitle files move with the video
- whether JavS removes the source directory after a successful sort
- the templates for file, folder, NFO, poster, screenshot, and trailer names

Recommended default:

- keep the default templates until you have confirmed the workflow on a small batch

When to change it:

- you want a different folder layout for Emby, Jellyfin, or your own library rules
- you want longer or shorter titles in folder names
- you want subtitles or cleanup behavior changed

Common mistakes:

- making several naming changes before running a preview sort
- enabling `cleanup_empty_source_dir` before confirming you like the output
- expecting sort templates to affect `update` folder placement; `update` stays in the current folder

Available template tokens:

- `{id}`
- `{title}`
- `{maker}`
- `{studio}`
- `{label}`
- `{series}`
- `{year}`
- `{director}`
- `{actresses}`

## NFO Options

NFO behavior lives under `sort.metadata.nfo`:

```yaml
sort:
  metadata:
    nfo:
      create: true
      display_name: "[{id}] {title}"
      add_aliases: false
      add_generic_role: true
      actress_as_tag: false
      original_path: false
      media_info: false
      format_tag:
        - "{set}"
```

What it controls:

- whether JavS writes NFO files at all
- how the display title appears in the NFO
- whether aliases, tags, roles, original path, or media info are added

Current path behavior:

- during `sort`, the NFO filename is derived from `sort.format.nfo`
- during `update`, JavS reuses an existing `<video basename>.nfo` when it finds one, otherwise a single existing NFO in the folder, otherwise it falls back to `sort.format.nfo`
- the schema still includes `sort.metadata.nfo.per_file`, but the current runtime does not consult that setting when choosing NFO paths

Recommended default:

- keep `create: true` and leave the extra enrichment flags off until you need them

When to change it:

- your media server expects a different display style
- you want more actress data or tags in the NFO
- you want the original source path embedded

Common mistakes:

- expecting `per_file` to change current NFO path generation by itself
- expecting NFO-only changes to rename folders or files
- enabling lots of metadata extras before checking whether your media server actually uses them

## CSV Templates

CSV-based overrides live under `sort.metadata.thumb_csv` and `sort.metadata.genre_csv`.

Starter example:

```yaml
locations:
  thumb_csv: ""
  genre_csv: ""

sort:
  metadata:
    thumb_csv:
      enabled: true
      auto_add: true
      convert_alias: true
    genre_csv:
      enabled: false
      auto_add: false
      ignored_patterns:
        - "^Featured Actress"
        - "^Hi-Def"
```

What it controls:

- `thumb_csv` fills in or normalizes actress thumbnail data
- `genre_csv` replaces, removes, or standardizes genres

Create local templates next to your config with:

```bash
./venv/bin/javs config init-csv
./venv/bin/javs config csv-paths
```

Recommended default:

- keep `thumb_csv` enabled
- keep `genre_csv` disabled until you know you want genre cleanup

When to change it:

- you want consistent actress thumbnail coverage
- you want to replace or suppress noisy genres

Common mistakes:

- enabling genre replacement without reviewing the generated CSV
- forgetting that `init-csv` also writes the resolved CSV paths into your config

## Translation

Translation lives under `sort.metadata.nfo.translate`:

```yaml
sort:
  metadata:
    nfo:
      translate:
        enabled: true
        module: deepl
        fields:
          - description
        language: en-us
        deepl_api_key: ""
        keep_original_description: false
        affect_sort_names: false
```

What it controls:

- whether selected metadata fields are translated
- which provider is used: `googletrans` or `deepl`
- which fields are translated
- whether translated text changes sort naming as well as NFO content

Recommended default:

- keep translation off until the normal scrape-and-sort flow is stable
- if you enable it, translate only `description` first
- keep `affect_sort_names: false` unless you want translated folder and file names

When to change it:

- you want readable descriptions in a different language
- you have a valid DeepL setup and want more consistent translations

Common mistakes:

- enabling translation without installing the translation extras
- using an invalid DeepL target code
- translating titles and enabling `affect_sort_names` before testing on a small batch

Install translation dependencies with:

```bash
./venv/bin/pip install -e ".[translate]"
```

You can also supply `DEEPL_API_KEY` in the environment instead of storing the key in the YAML file.

## Proxy

Proxy settings live under `proxy`:

```yaml
proxy:
  enabled: false
  url: ""
  timeout_seconds: 15
  max_retries: 3
```

What it controls:

- whether JavS uses a proxy at all
- the proxy URL, timeout, and retry settings

Supported URL schemes:

- `http://`
- `https://`
- `socks5://`
- `socks5h://`

Recommended default:

- leave proxy disabled unless you know you need it

When to change it:

- a source is region-blocked or only works through your proxy
- your environment requires outbound proxying

Common mistakes:

- setting `proxy.enabled: true` without a URL
- omitting the URL scheme
- assuming all scrapers use the proxy automatically

Test the current proxy config with:

```bash
./venv/bin/javs config proxy-test
```

That command checks whether the configured proxy is enabled, reachable, and able to complete a simple proxied request.

## Javlibrary Credentials

Javlibrary-specific values live under `javlibrary`:

```yaml
javlibrary:
  base_url: "https://www.javlibrary.com"
  browser_user_agent: ""
  cookie_cf_clearance: ""
```

What it controls:

- the base URL JavS uses for Javlibrary
- the Cloudflare values needed when Javlibrary blocks normal requests

Recommended default:

- keep Javlibrary disabled until `r18dev` and `dmm` are working for you

When to change it:

- you explicitly want Javlibrary as a data source
- the CLI reports Cloudflare blocking for Javlibrary

Use the helper commands instead of editing these values blindly:

```bash
./venv/bin/javs config javlibrary-cookie
./venv/bin/javs config javlibrary-test
```

Common mistakes:

- saving `cookie_cf_clearance` without the matching browser user agent
- enabling Javlibrary and assuming it will work without Cloudflare recovery
- leaving stale credentials in place after Cloudflare expires them

## Config Sync

Use config sync when the project adds or changes supported config keys:

```bash
./venv/bin/javs config sync
```

What it does:

- merges your current config with the latest packaged template
- preserves your customizations while pulling in current schema defaults

Recommended use:

- run it after upgrading JavS
- run it when the docs or release notes mention new config fields

Common mistakes:

- editing old keys manually and forgetting to pull in the new template structure
- treating sync as a substitute for reviewing your own custom settings

After sync, run:

```bash
./venv/bin/javs config show
```

That gives you a quick masked view of the final effective config.
