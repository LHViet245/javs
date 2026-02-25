"""Data models for movie metadata, actresses, and ratings."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class Actress(BaseModel):
    """Represents a single actress/performer."""

    last_name: str | None = None
    first_name: str | None = None
    japanese_name: str | None = None
    thumb_url: str | None = None
    english_aliases: list[ActressAlias] = Field(default_factory=list)
    japanese_aliases: list[JapaneseAlias] = Field(default_factory=list)

    @property
    def full_name(self) -> str:
        """Return full name in 'LastName FirstName' order."""
        parts = [p for p in [self.last_name, self.first_name] if p]
        return " ".join(parts) if parts else self.japanese_name or "Unknown"

    @property
    def full_name_reversed(self) -> str:
        """Return full name in 'FirstName LastName' order."""
        parts = [p for p in [self.first_name, self.last_name] if p]
        return " ".join(parts) if parts else self.japanese_name or "Unknown"


class ActressAlias(BaseModel):
    """English name alias for an actress."""

    last_name: str | None = None
    first_name: str | None = None


class JapaneseAlias(BaseModel):
    """Japanese name alias for an actress."""

    japanese_name: str


class Rating(BaseModel):
    """Movie rating with vote count."""

    rating: float = Field(ge=0, le=10)
    votes: int | None = Field(default=None, ge=0)


class MovieData(BaseModel):
    """Core metadata for a single JAV movie, scraped from one or more sources."""

    id: str = ""
    content_id: str | None = None
    title: str | None = None
    alternate_title: str | None = None
    display_name: str | None = None
    description: str | None = None
    rating: Rating | None = None
    release_date: date | None = None
    runtime: int | None = None  # minutes
    director: str | None = None
    maker: str | None = None
    label: str | None = None
    series: str | None = None
    genres: list[str] = Field(default_factory=list)
    actresses: list[Actress] = Field(default_factory=list)
    cover_url: str | None = None
    screenshot_urls: list[str] = Field(default_factory=list)
    trailer_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    tagline: str | None = None
    credits: list[str] = Field(default_factory=list)
    source: str = ""  # scraper name that produced this data

    # Internal tracking
    original_filename: str | None = None
    media_info: MediaInfo | None = None

    @property
    def release_year(self) -> int | None:
        return self.release_date.year if self.release_date else None


class MediaInfo(BaseModel):
    """Technical media information from a video file."""

    video_codec: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_aspect: str | None = None
    video_duration: int | None = None  # seconds
    audio_codec: str | None = None
    audio_channels: int | None = None
    audio_language: str | None = None


class ScraperSourceEnum(StrEnum):
    """Enumeration of all supported scraper sources."""

    DMM = "dmm"
    DMM_JA = "dmmja"
    R18DEV = "r18dev"
    JAVLIBRARY = "javlibrary"
    JAVLIBRARY_JA = "javlibraryja"
    JAVLIBRARY_ZH = "javlibraryzh"
    JAVBUS = "javbus"
    JAVBUS_JA = "javbusja"
    JAVBUS_ZH = "javbuszh"
    JAVDB = "javdb"
    JAVDB_ZH = "javdbzh"
    JAV321_JA = "jav321ja"
    MGSTAGE_JA = "mgstageja"
    AVENTERTAINMENT = "aventertainment"
    AVENTERTAINMENT_JA = "aventertainmentja"
    TOKYOHOT = "tokyohot"
    TOKYOHOT_JA = "tokyohotja"
    TOKYOHOT_ZH = "tokyohotzh"
    DLGETCHU_JA = "dlgetchuja"
