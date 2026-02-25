"""String formatting utilities for movie metadata."""

from __future__ import annotations

import html
import re
import unicodedata


def clean_title(title: str) -> str:
    """Clean and normalize a movie title string.

    Removes extra whitespace, HTML entities, and normalizes unicode.
    """
    if not title:
        return ""
    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title).strip()
    title = unicodedata.normalize("NFKC", title)
    return title


def clean_html(text: str) -> str:
    """Remove HTML tags from a string."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def truncate(text: str, max_length: int = 100) -> str:
    """Truncate a string to max_length characters."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length].rstrip()


def format_template(
    template: str,
    data: dict,
    delimiter: str = ", ",
    max_title_length: int = 100,
) -> str:
    """Format a naming template with movie data.

    Supports placeholders: {id}, {title}, {studio}, {year}, {actress},
    {label}, {series}, {director}, {set}

    Args:
        template: Format string with {placeholders}.
        data: Dictionary of values to substitute.
        delimiter: Separator for list values (actresses).
        max_title_length: Max length for title before truncation.

    Returns:
        Formatted string.
    """
    # Normalize the template to use lowercase keys
    result = template

    replacements = {
        "{id}": data.get("id", ""),
        "{ID}": data.get("id", ""),
        "{title}": truncate(data.get("title", ""), max_title_length),
        "{TITLE}": truncate(data.get("title", ""), max_title_length),
        "{studio}": data.get("maker", ""),
        "{STUDIO}": data.get("maker", ""),
        "{year}": str(data.get("year", "")),
        "{YEAR}": str(data.get("year", "")),
        "{label}": data.get("label", ""),
        "{LABEL}": data.get("label", ""),
        "{series}": data.get("series", ""),
        "{SERIES}": data.get("series", ""),
        "{SET}": data.get("series", ""),
        "{set}": data.get("series", ""),
        "{director}": data.get("director", ""),
        "{DIRECTOR}": data.get("director", ""),
    }

    # Handle actress - can be a list
    actresses = data.get("actresses", [])
    if isinstance(actresses, list):
        actress_str = delimiter.join(actresses)
    else:
        actress_str = str(actresses)
    replacements["{actress}"] = actress_str
    replacements["{ACTRESS}"] = actress_str

    for placeholder, value in replacements.items():
        result = result.replace(placeholder, str(value) if value else "")

    # Also handle Javinizer-style <PLACEHOLDER> for backward compatibility
    jv_replacements = {
        "<ID>": data.get("id", ""),
        "<TITLE>": truncate(data.get("title", ""), max_title_length),
        "<STUDIO>": data.get("maker", ""),
        "<YEAR>": str(data.get("year", "")),
        "<LABEL>": data.get("label", ""),
        "<SERIES>": data.get("series", ""),
        "<SET>": data.get("series", ""),
        "<DIRECTOR>": data.get("director", ""),
        "<ACTRESS>": actress_str,
    }

    for placeholder, value in jv_replacements.items():
        result = result.replace(placeholder, str(value) if value else "")

    # Clean up empty brackets and double spaces
    result = re.sub(r"\[\s*\]", "", result)
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r"\s{2,}", " ", result).strip()
    result = result.rstrip(" -").rstrip()

    return result


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames across platforms."""
    # Replace common problematic characters
    invalid_chars = r'[<>:"/\\|?*]'
    result = re.sub(invalid_chars, "_", name)
    # Remove trailing dots/periods (Windows issue)
    result = result.rstrip(".")
    return result


def is_japanese(text: str) -> bool:
    """Check if text contains Japanese characters (Hiragana, Katakana, Kanji)."""
    if not text:
        return False
    return bool(re.search(r"[\u3040-\u309f\u30a0-\u30ff\uff66-\uff9f\u4e00-\u9faf]", text))
