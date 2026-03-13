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
- **Scrapers:** Enable/disable scrapers and set their languages (e.g., `javlibrary` vs `javlibrary_ja`).
- **Renaming:** Configure how files are sorted and renamed.
- **NFOs:** Format settings for Emby/Jellyfin/Kodi NFOs.

To view the current configuration:

```bash
javs config show
```

To edit the configuration (opens your default text editor):

```bash
javs config edit
```

To automatically update and merge your local configuration with the latest defaults (while preserving your customizations and comments):

```bash
javs config sync
```

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

### 3. `scrapers` - Manage Plugins

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
- Bypasses Cloudflare automatically for search queries.

---

## ⚙️ Development & Testing

JavS has a rigorous testing suite covering 100% of the core paths.

```bash
# Run full suite
./venv/bin/python -m pytest tests/ -v

# Run only scraper tests
./venv/bin/python -m pytest tests/scrapers/ -v
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
