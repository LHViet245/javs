"""Shared application-layer contracts for CLI and future API adapters."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from javs.config import JavsConfig
from javs.models.movie import MovieData

_MOVIE_ID_PATTERN = re.compile(r"([A-Z]+)(\d+)")


def _normalize_movie_id(value: str) -> str:
    movie_id = value.strip().upper()

    if "-" in movie_id:
        prefix, suffix = movie_id.split("-", 1)
        if not prefix.isalpha() or not suffix.isdigit():
            return movie_id
        number = suffix.lstrip("0") or "0"
        return f"{prefix}-{number.zfill(3)}"

    match = _MOVIE_ID_PATTERN.fullmatch(movie_id)
    if match is None:
        return movie_id

    prefix, number = match.groups()
    return f"{prefix}-{(number.lstrip('0') or '0').zfill(3)}"


def _normalize_scraper_names(value: object) -> object:
    if value is None:
        return None

    raw_names: list[object]
    if isinstance(value, str):
        raw_names = [value]
    elif isinstance(value, list | tuple | set):
        raw_names = list(value)
    else:
        return value

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_names:
        name = str(item).strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(name)

    return normalized or None


class FindMovieRequest(BaseModel):
    """Request contract for looking up a single movie."""

    movie_id: str
    scraper_names: list[str] | None = None

    @field_validator("movie_id", mode="before")
    @classmethod
    def normalize_movie_id(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_movie_id(value)
        return value

    @field_validator("scraper_names", mode="before")
    @classmethod
    def normalize_scraper_names(cls, value: object) -> object:
        return _normalize_scraper_names(value)


class SortJobRequest(BaseModel):
    """Request contract for a shared sort job."""

    source_path: str
    destination_path: str | None = None


class UpdateJobRequest(BaseModel):
    """Request contract for a shared update job."""

    source_path: str


class SaveSettingsRequest(BaseModel):
    """Request contract for persisting validated settings changes."""

    changes: dict[str, Any] = Field(default_factory=dict)
    source_path: str | None = None


class JobSummary(BaseModel):
    """Top-level summary returned for jobs and job lists."""

    id: str
    kind: str
    status: str
    origin: str
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    summary: dict[str, Any] | None = None
    error: dict[str, Any] | None = None


class JobItemSummary(BaseModel):
    """Item-level progress summary for sort and update jobs."""

    id: int
    item_key: str
    status: str
    source_path: str | None = None
    dest_path: str | None = None
    movie_id: str | None = None
    step: str | None = None
    message: str | None = None
    metadata: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class JobDetail(BaseModel):
    """Expanded job details, including stored result and item history."""

    job: JobSummary
    result: dict[str, Any] | None = None
    items: list[JobItemSummary] = Field(default_factory=list)


class JobStartResponse(BaseModel):
    """Response returned when a shared job is created."""

    job: JobSummary


class FindMovieResponse(BaseModel):
    """Response contract for a completed find request."""

    job: JobSummary
    result: MovieData | None = None


class SettingsResponse(BaseModel):
    """Response contract for reading the active YAML-backed settings."""

    config: JavsConfig
    source_path: str
    config_version: int


class SaveSettingsResponse(BaseModel):
    """Response contract for saving settings through the shared facade."""

    job: JobSummary
    settings: SettingsResponse
