"""Models for scanned files and sort output paths."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ScannedFile(BaseModel):
    """A video file detected and parsed by the file scanner."""

    path: Path
    filename: str
    basename: str  # filename without extension
    extension: str
    directory: Path
    size_bytes: int
    movie_id: str
    part_number: int | None = None  # for multi-part movies

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


class SortPaths(BaseModel):
    """All output paths generated for a sorted movie."""

    folder_path: Path
    folder_name: str
    file_path: Path
    file_name: str
    nfo_path: Path
    thumb_path: Path
    poster_paths: list[Path] = Field(default_factory=list)
    trailer_path: Path | None = None
    screenshot_folder_path: Path | None = None
    screenshot_img_name: str = "fanart"
    actor_folder_path: Path | None = None
    parent_path: Path | None = None
    part_number: int = 0

    # For rename-in-place mode
    rename_new_path: Path | None = None
