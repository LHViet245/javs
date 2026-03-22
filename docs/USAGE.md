# JavS Usage Guide

**JavS** is a fast, async-native Python CLI for scraping, organizing, and managing JAV media libraries. It replaces the original Javinizer with better performance, a modular plugin system, and automated metadata scraping.

---

## 🚀 Quick Setup

JavS is entirely driven by Python `venv` to prevent dependency conflicts.

```bash
# First time setup
cd javs
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
```

Then run commands using:

```bash
./venv/bin/javs [command]
```

Or activate the environment:

```bash
source venv/bin/activate
javs [command]
```

---

## 🛠️ Configuration

Configuration is automatically generated on your first run. You can configure:

- **Priorities:** Define which scrapers to trust most if data contradicts.
- **Scrapers:** Enable/disable scrapers and set their languages (e.g., `javlibrary` vs `javlibraryja`).
- **Renaming:** Configure how files are sorted and renamed.
- **NFOs:** Format settings for Emby/Jellyfin/Kodi NFOs.

To view the current configuration:

```bash
./venv/bin/javs config show
```

To edit the configuration (opens your default text editor):

```bash
./venv/bin/javs config edit
```

To automatically update and merge your local configuration with the latest defaults (while preserving your customizations and comments):

```bash
./venv/bin/javs config sync
```

File detection supports three matching modes in `match.mode`:

- `auto`: default built-in detection, widest filename coverage
- `strict`: only match strongly bounded dashed IDs such as `ABP-420`
- `custom`: use your own `match.regex` pattern

`strict` still supports multipart suffixes like `-pt2` and `A/B` when the base ID was matched clearly.

JavS also supports two local CSV customizations in the aggregator layer:

- `locations.genre_csv`: optional path override for `genres.csv`
- `locations.thumb_csv`: optional path override for `thumbs.csv`

Default templates now live in `javs/data/genres.csv` and `javs/data/thumbs.csv`.
When enabled, `genre_csv` can replace or remove genres, and `thumb_csv` can fill in missing
actress thumbnails. `auto_add` lets JavS append new genres or actresses it encounters to those
CSV files for later curation.

To enter Javlibrary Cloudflare credentials without editing YAML manually:

```bash
./venv/bin/javs config javlibrary-cookie
./venv/bin/javs config javlibrary-test
```

`javlibrary-cookie` always asks for a fresh `cf_clearance`. It only asks for
`browser_user_agent` when that value is still empty in your config.

---

## 🔎 Key Commands

### 1. `find` - Manual Metadata Search

Search for a specific ID with visual output in the terminal.

```bash
javs find "ABP-420"
```

The tool will query all active scrapers in parallel, aggregate the best data according to your priorities, and display a rich summary of the movie (Title, Actresses, Genres, Maker, Cover URL, etc.).

### 2. `sort` - Auto-Organize Media

Scan directories, identify movie IDs in filenames, fetch metadata, create `.nfo` files, download cover art, and move files to standardized directories.

```bash
# Sort a directory, move to the destination directory, scan recursively
javs sort /path/to/unsorted /path/to/vidstream --recurse
```

**Sorting Workflow:**

1. Scans the input path for supported video extensions (`.mp4`, `.mkv`, etc.).
2. Extracts potential IDs (e.g., `ABP-420` from `[Thz.la]ABP-420.1080p.mp4`).

   **Supported formats:**
   - Standard: `ABP-123.mp4`, `SSIS-001.mkv`
   - Numeric Prefix: `259LUXU-123.mp4`
   - Multi-part: `ABP-123 cd1.mp4`, `ABP-123 pt2.mp4`, `DVMM-377A.mp4`, `DVMM-377B.mp4`
   - With Uncensored Tag: `RCTD-717_uncensored.mp4`
   - Subtitle tags like `-C` will NOT be mistaken for part numbers.

   **Note on Directory Names:**
   JavS's `sort` command explicitly scans **filenames**, not parent directory names. If your video is generic (e.g., `SGKI-079/video.mp4`), the engine will skip it. Please rename the file itself to contain the ID (e.g., `SGKI-079/video.mp4` -> `SGKI-079/SGKI-079.mp4`) before running the sort command.

3. Fetches best-matched metadata from `dmm`, `r18dev`, `javlibrary`, etc.
4. Downloads poster/cover images.
5. Generates Kodi/Emby compatible `<id>.nfo`.
6. Renames and moves the files according to config (e.g., `Sorted/Maker - Title/ID.mp4`).

### 3. `update` - Refresh an Existing Sorted Library

Refresh metadata sidecars for videos that are already organized in-place. This command re-scans
video filenames to extract IDs, scrapes fresh metadata, and updates files inside the current movie
folder without moving or renaming the video itself.

```bash
# Refresh NFO/metadata in place
javs update /path/to/vidstream --recurse

# Re-download existing images and trailer as well
javs update /path/to/vidstream --recurse --refresh-images --refresh-trailer
```

**Update behavior:**

1. Scans the sorted library for supported video files and extracts movie IDs from filenames.
2. Scrapes fresh metadata from the selected scrapers.
3. Rewrites the `.nfo` in the current movie folder.
4. Keeps the current video file and folder in place.
5. Re-downloads posters/thumbs/screenshots/actress images only when requested with `--refresh-images`.
6. Re-downloads the trailer only when requested with `--refresh-trailer`.

This is intended for already-sorted libraries where you want better metadata without triggering a
new move/rename pass.

### 4. `scrapers` - Manage Plugins

List all recognized and registered scraper plugins:

```bash
javs scrapers
```

Outputs the scraper names (e.g., `dmm`, `r18dev`, `javlibrary`, `javlibraryja`, `javlibraryzh`) and their active status.

---

## 🧰 Available Scrapers

JavS currently includes several high-quality scrapers.

### **DMM (`dmm`)**

The official DMM store scraper.

- Extremely high accuracy and official tags.
- Provides standard format actress names.
- Excellent source for high-quality un-cropped covers and screenshots.

### **R18Dev (`r18dev`)**

A fast JSON API.

- Excellent fallback.
- Contains English and Japanese aliases seamlessly.
- Includes JSON-based screenshot endpoints.

### **JAVLibrary (`javlibrary`, `javlibraryja`, `javlibraryzh`)**

The largest community database.

- Has User Ratings (score).
- Connects English and Japanese variants for multi-language actress matching.
- Tracks aliases across different productions.
- Supports manual `cf_clearance` input when Cloudflare blocks access, while reusing the saved `browser_user_agent`.
- During interactive CLI runs, JavS can prompt for refreshed Javlibrary credentials and retry once.

---

## ⚙️ Development & Testing

JavS has a fast local test suite focused on mocked HTTP flows, parser fixtures, and core pipeline contracts.

```bash
# Run full suite
./venv/bin/python -m pytest tests -q

# Run only scraper tests
./venv/bin/python -m pytest tests/scrapers -q
```

### Writing a new Scraper

Creating plugins is easy. Extend `BaseScraper` and register it:

```python
from javs.scrapers.base import BaseScraper
from javs.scrapers.registry import ScraperRegistry

@ScraperRegistry.register
class MyScraper(BaseScraper):
    name = "myscraper"
    display_name = "My Target Site"
    languages = ["en"]
    
    async def search(self, movie_id: str) -> str | None:
        # Return URL to detail page
        return "https://site.com/video/" + movie_id

    async def scrape(self, url: str) -> MovieData | None:
        # Fetch, parse, and return MovieData
        html = await self.http.get(url)
        return MovieData(...)
```

No core code editing required! The aggregator automatically picks it up based on your `config.yaml`.
