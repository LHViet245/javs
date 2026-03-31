"""Configuration models using Pydantic for type-safe settings management."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RegexConfig(BaseModel):
    """Custom regex pattern for filename matching."""

    pattern: str = r"([a-zA-Z|tT28]+-\d+[zZ]?[eE]?)(?:-pt)?(\d{1,2})?"
    id_match_group: int = 1
    part_match_group: int = 2


class MatchConfig(BaseModel):
    """File matching/detection settings."""

    mode: Literal["auto", "strict", "custom"] = "auto"
    minimum_file_size_mb: int = 0
    included_extensions: list[str] = Field(
        default_factory=lambda: [
            ".asf",
            ".avi",
            ".flv",
            ".m4v",
            ".mkv",
            ".mp4",
            ".mov",
            ".rmvb",
            ".wmv",
        ]
    )
    excluded_patterns: list[str] = Field(default_factory=lambda: [r"^.*-trailer*", r"^.*-5\."])
    regex_enabled: bool = False
    regex: RegexConfig = Field(default_factory=RegexConfig)

    @model_validator(mode="before")
    @classmethod
    def preserve_legacy_custom_regex_mode(cls, data: object) -> object:
        """Map legacy regex_enabled=true configs to custom mode when mode is absent."""
        if isinstance(data, dict) and "mode" not in data and data.get("regex_enabled") is True:
            data = dict(data)
            data["mode"] = "custom"
        return data


class FormatConfig(BaseModel):
    """File/folder naming format templates."""

    file: str = "{id}"
    folder: str = "{id} [{studio}] - {title} ({year})"
    poster_img: list[str] = Field(default_factory=lambda: ["folder"])
    thumb_img: str = "fanart"
    trailer_vid: str = "{id}-trailer"
    nfo: str = "{id}"
    screenshot_img: str = "fanart"
    screenshot_padding: int = 1
    screenshot_folder: str = "extrafanart"
    actress_img_folder: str = ".actors"
    delimiter: str = ", "
    max_title_length: int = 100


class DownloadConfig(BaseModel):
    """Media download settings."""

    actress_img: bool = False
    thumb_img: bool = True
    poster_img: bool = True
    screenshot_img: bool = False
    trailer_vid: bool = False
    timeout_seconds: int = 100


class TranslateConfig(BaseModel):
    """Translation settings."""

    enabled: bool = False
    module: str = "googletrans"  # "googletrans" or "deepl"
    fields: list[str] = Field(default_factory=lambda: ["description"])
    language: str = "en-us"
    deepl_api_key: str = ""
    keep_original_description: bool = False
    affect_sort_names: bool = False


class NfoConfig(BaseModel):
    """NFO generation settings."""

    create: bool = True
    per_file: bool = True
    add_aliases: bool = False
    add_generic_role: bool = True
    alt_name_role: bool = False
    display_name: str = "[{id}] {title}"
    first_name_order: bool = False
    actress_language_ja: bool = False
    unknown_actress: bool = True
    original_path: bool = False
    actress_as_tag: bool = False
    prefer_actress_alias: bool = False
    media_info: bool = False
    format_tag: list[str] = Field(default_factory=lambda: ["{set}"])
    format_tagline: str = ""
    format_credits: list[str] = Field(default_factory=list)
    translate: TranslateConfig = Field(default_factory=TranslateConfig)


class MetadataPriorityConfig(BaseModel):
    """Priority order for each metadata field across scrapers."""

    actress: list[str] = Field(default_factory=lambda: ["r18dev", "dmm", "javlibrary"])
    alternate_title: list[str] = Field(default_factory=lambda: ["javlibraryja", "dmm"])
    cover_url: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "dmm"])
    description: list[str] = Field(default_factory=lambda: ["dmm", "r18dev", "mgstageja"])
    director: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "mgstageja"])
    genre: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary"])
    id: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary"])
    content_id: list[str] = Field(default_factory=lambda: ["r18dev", "dmm"])
    label: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "mgstageja"])
    maker: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary"])
    release_date: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "dmm"])
    rating: list[str] = Field(default_factory=lambda: ["dmm", "javlibrary", "mgstageja"])
    runtime: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "dmm"])
    series: list[str] = Field(default_factory=lambda: ["r18dev", "mgstageja"])
    screenshot_url: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary", "dmm"])
    title: list[str] = Field(default_factory=lambda: ["r18dev", "javlibrary"])
    trailer_url: list[str] = Field(default_factory=lambda: ["r18dev", "dmm"])


class ThumbCsvConfig(BaseModel):
    """Actress thumbnail CSV settings."""

    enabled: bool = True
    auto_add: bool = True
    convert_alias: bool = True


class GenreCsvConfig(BaseModel):
    """Genre replacement CSV settings."""

    enabled: bool = False
    auto_add: bool = False
    ignored_patterns: list[str] = Field(
        default_factory=lambda: [r"^Featured Actress", r"^Hi-Def", r".*sale.*", r".*mosaic.*"]
    )


class MetadataConfig(BaseModel):
    """Metadata processing settings."""

    nfo: NfoConfig = Field(default_factory=NfoConfig)
    priority: MetadataPriorityConfig = Field(default_factory=MetadataPriorityConfig)
    thumb_csv: ThumbCsvConfig = Field(default_factory=ThumbCsvConfig)
    genre_csv: GenreCsvConfig = Field(default_factory=GenreCsvConfig)
    required_fields: list[str] = Field(
        default_factory=lambda: ["id", "cover_url", "genres", "maker", "release_date", "title"]
    )


class SortConfig(BaseModel):
    """File sorting/organization settings."""

    move_to_folder: bool = True
    rename_file: bool = True
    move_subtitles: bool = True
    cleanup_empty_source_dir: bool = False
    format: FormatConfig = Field(default_factory=FormatConfig)
    download: DownloadConfig = Field(default_factory=DownloadConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)


class ScraperConfig(BaseModel):
    """Which scrapers are enabled and proxy routing."""

    enabled: dict[str, bool] = Field(
        default_factory=lambda: {
            "r18dev": True,
            "dmm": True,
            "javlibrary": False,
            "javlibraryja": False,
            "javlibraryzh": False,
            "mgstageja": False,
        }
    )
    use_proxy: dict[str, bool] = Field(
        default_factory=lambda: {
            "r18dev": False,
            "dmm": True,  # Japan region block
            "javlibrary": False,
            "javlibraryja": False,
            "javlibraryzh": False,
            "mgstageja": True,  # Japan region block
        }
    )


class ProxyConfig(BaseModel):
    """Proxy settings.

    Supports HTTP, HTTPS, SOCKS5, and SOCKS5h protocols.
    URL format: protocol://[user:pass@]host:port
    Examples:
        - http://1.2.3.4:8080
        - http://myuser:mypass@1.2.3.4:8080
        - socks5://1.2.3.4:1080
        - socks5h://1.2.3.4:1080  (proxy-side DNS resolution)
    """

    enabled: bool = False
    url: str = ""
    timeout_seconds: int = 15
    max_retries: int = 3

    @model_validator(mode="after")
    def validate_proxy(self) -> ProxyConfig:
        """Validate proxy config: require URL when enabled, require protocol."""
        if self.enabled and not self.url:
            raise ValueError("proxy.url is required when proxy.enabled is True")
        if self.url and "://" not in self.url:
            raise ValueError(
                "proxy.url must include protocol (http://, https://, socks5://, socks5h://)"
            )
        return self

    @property
    def masked_url(self) -> str:
        """Return URL with credentials replaced by *** for safe logging."""
        if not self.url:
            return ""
        try:
            from yarl import URL

            parsed = URL(self.url)
            if parsed.password:
                return str(parsed.with_password("***").with_user("***"))
        except Exception:
            pass
        return self.url

    @property
    def is_socks(self) -> bool:
        """Check if proxy uses SOCKS protocol."""
        return self.url.startswith(("socks4", "socks5"))


class EmbyConfig(BaseModel):
    """Emby/Jellyfin server settings."""

    url: str = "http://192.168.0.1:8096"
    api_key: str = ""


class JavlibraryConfig(BaseModel):
    """Javlibrary-specific settings used by the runtime."""

    base_url: str = "https://www.javlibrary.com"
    browser_user_agent: str = ""
    cookie_cf_clearance: str = ""


class LocationConfig(BaseModel):
    """Custom path overrides for data files."""

    input: str = ""
    output: str = ""
    thumb_csv: str = ""
    genre_csv: str = ""
    log: str = ""


class LogConfig(BaseModel):
    """Logging settings."""

    enabled: bool = True
    level: str = "info"  # debug, info, warning, error


class JavsConfig(BaseModel):
    """Root configuration model for javs."""

    # Processing
    throttle_limit: int = 1
    sleep: int = 2

    # Locations
    locations: LocationConfig = Field(default_factory=LocationConfig)

    # Core modules
    scrapers: ScraperConfig = Field(default_factory=ScraperConfig)
    match: MatchConfig = Field(default_factory=MatchConfig)
    sort: SortConfig = Field(default_factory=SortConfig)

    # External services
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    emby: EmbyConfig = Field(default_factory=EmbyConfig)

    # Source-specific
    javlibrary: JavlibraryConfig = Field(default_factory=JavlibraryConfig)

    log: LogConfig = Field(default_factory=LogConfig)
