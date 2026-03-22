# JavS 🎬

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> A fast, async-native Python CLI for scraping, organizing, and managing JAV media libraries.

**JavS** is a complete, modern rewrite of [Javinizer](https://github.com/javinizer/Javinizer) in Python. It features a scalable architecture, high concurrency with `asyncio`, type safety with `pydantic`, and a robust plugin system for scrapers.

---

## ✨ Features

- ⚡ **High Performance:** Fully asynchronous scraping (`aiohttp`) fetches from multiple sources simultaneously.
- 🧩 **Plugin Architecture:** Easily extendable. Write a scraper class and it automatically integrates.
- 🎯 **Smart Aggregation:** Fetches from multiple sites (DMM, R18Dev, JavLibrary, etc.) and seamlessly merges the best metadata based on your custom priority rules.
- 🌐 **Translation Service:** Built-in async wrappers for `googletrans` and `deepl` to translate metadata automatically.
- 🗂️ **Automated Organization:** Identifies IDs and Multi-parts (cd, pt, A/B) in filenames, downloads covers/posters, generates NFOs (Kodi/Emby/Jellyfin compatible), and strictly organizes your media folders.
- ♻️ **In-Place Metadata Refresh:** Re-scan an already sorted library to refresh NFO and metadata sidecars without moving video files, with optional image and trailer re-downloads.
- ⚙️ **Config Sync:** Merge the latest default template into your local config while preserving supported overrides and YAML comments using `ruamel.yaml` (`./venv/bin/javs config sync`).
- 🧩 **Javlibrary Recovery:** When Javlibrary hits Cloudflare, you can refresh `cf_clearance` from the CLI (`./venv/bin/javs config javlibrary-cookie`) instead of editing YAML by hand; `browser_user_agent` is reused from config once saved.
- 🛡️ **Type Safety:** Built on `pydantic` ensuring strict data validation for all metadata and configurations.

## ⚠️ Quy tắc bắt buộc: Virtual Environment

> **Mọi thao tác cài đặt package, chạy code, và test đều PHẢI thực hiện trong môi trường ảo `venv`.**
>
> Sử dụng `./venv/bin/python` thay vì `python` của hệ thống.

```bash
# Cài đặt package
./venv/bin/pip install -e ".[dev]"

# Chạy code
./venv/bin/python -m javs
./venv/bin/javs --help

# Chạy tests
./venv/bin/python -m pytest tests/ -v
```

## 🚀 Quick Start

1. **Clone & Setup:**

```bash
git clone https://github.com/LHViet245/javs.git
cd javs
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
```

2. **Run a Test Search:**

```bash
./venv/bin/javs find "ABP-420"
```

3. **Organize a Directory:**

```bash
./venv/bin/javs sort /path/to/unsorted /path/to/vidstream --recurse
```

4. **Refresh an Existing Sorted Library:**

```bash
./venv/bin/javs update /path/to/vidstream --recurse
./venv/bin/javs update /path/to/vidstream --recurse --refresh-images --refresh-trailer
```

## 📖 Documentation

For detailed guides, please see the [**Usage Guide**](docs/USAGE.md).

- [Configuration Guide](docs/USAGE.md#%EF%B8%8F-configuration)
- [Available Commands](docs/USAGE.md#-key-commands)
- [Scraper Plugins](docs/USAGE.md#-available-scrapers)
- [Development & Testing](docs/USAGE.md#%E2%9A%99%EF%B8%8F-development--testing)

## 🏗️ Architecture

- **Core Framework:** Python 3.11+, `asyncio`, `aiohttp`
- **CLI Interface:** `Typer` / `Rich` for beautiful terminal output
- **Data Models:** `Pydantic` validation
- **Testing:** `pytest` + `pytest-asyncio` with local fixtures and mocked HTTP responses
- **Logging:** Structured JSON logs via `structlog`

## 🤝 Contributing

Contributions are welcome! Please ensure all tests pass (`./venv/bin/python -m pytest tests -q`) and lint is clean (`./venv/bin/python -m ruff check javs tests`) before submitting a PR.
