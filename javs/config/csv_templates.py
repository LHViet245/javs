"""Helpers for packaged CSV templates and user-local CSV initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile

from javs.config.loader import save_config
from javs.config.models import JavsConfig


@dataclass(slots=True)
class CsvInitResult:
    """Summary of CSV template initialization."""

    genre_csv_path: Path
    thumb_csv_path: Path
    created: list[Path]
    existing: list[Path]


def get_packaged_csv_template_path(filename: str) -> Path:
    """Return the packaged CSV template path."""
    return Path(__file__).parent.parent / "data" / filename


def get_effective_csv_paths(config: JavsConfig, config_path: Path) -> dict[str, Path]:
    """Return active CSV paths for the current config."""
    defaults = get_user_csv_default_paths(config_path)
    return {
        "genres.csv": (
            Path(config.locations.genre_csv)
            if config.locations.genre_csv
            else defaults["genres.csv"]
        ),
        "thumbs.csv": (
            Path(config.locations.thumb_csv)
            if config.locations.thumb_csv
            else defaults["thumbs.csv"]
        ),
    }


def get_user_csv_default_paths(config_path: Path) -> dict[str, Path]:
    """Return default user-local CSV destinations next to the config file."""
    config_dir = config_path.parent
    return {
        "genres.csv": config_dir / "genres.csv",
        "thumbs.csv": config_dir / "thumbs.csv",
    }


def init_csv_templates(config: JavsConfig, config_path: Path) -> CsvInitResult:
    """Copy packaged CSV templates to user-local paths and persist config overrides."""
    effective_paths = get_effective_csv_paths(config, config_path)
    created: list[Path] = []
    existing: list[Path] = []

    for filename, destination in effective_paths.items():
        template = get_packaged_csv_template_path(filename)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing.append(destination)
            continue
        copyfile(template, destination)
        created.append(destination)

    config.locations.genre_csv = str(effective_paths["genres.csv"])
    config.locations.thumb_csv = str(effective_paths["thumbs.csv"])
    save_config(config, config_path)

    return CsvInitResult(
        genre_csv_path=effective_paths["genres.csv"],
        thumb_csv_path=effective_paths["thumbs.csv"],
        created=created,
        existing=existing,
    )
