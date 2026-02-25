"""HTML parsing helper utilities."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag


def parse_html(content: str, parser: str = "lxml") -> BeautifulSoup:
    """Parse HTML content into a BeautifulSoup object.

    Args:
        content: Raw HTML string.
        parser: Parser to use (lxml recommended for speed).

    Returns:
        Parsed BeautifulSoup object.
    """
    return BeautifulSoup(content, parser)


def extract_text(element: Tag | None, default: str = "") -> str:
    """Safely extract text from a BeautifulSoup element.

    Args:
        element: BS4 Tag element or None.
        default: Value to return if element is None.

    Returns:
        Stripped text content.
    """
    if element is None:
        return default
    return element.get_text(strip=True)


def extract_attr(element: Tag | None, attr: str, default: str = "") -> str:
    """Safely extract an attribute from a BeautifulSoup element.

    Args:
        element: BS4 Tag element or None.
        attr: Attribute name (e.g., 'href', 'src').
        default: Value to return if element or attr is None.

    Returns:
        Attribute value.
    """
    if element is None:
        return default
    value = element.get(attr)
    if isinstance(value, list):
        return value[0] if value else default
    return value or default


def select_one_text(soup: BeautifulSoup, selector: str, default: str = "") -> str:
    """Select one element and return its text.

    Args:
        soup: BeautifulSoup object to search.
        selector: CSS selector string.
        default: Value if not found.

    Returns:
        Text content.
    """
    el = soup.select_one(selector)
    return extract_text(el, default)


def select_all_text(soup: BeautifulSoup, selector: str) -> list[str]:
    """Select all matching elements and return their text.

    Args:
        soup: BeautifulSoup object to search.
        selector: CSS selector string.

    Returns:
        List of text strings.
    """
    return [extract_text(el) for el in soup.select(selector) if extract_text(el)]


def regex_extract(content: str, pattern: str, group: int = 1, default: str = "") -> str:
    """Extract content using a regex pattern.

    Args:
        content: String to search.
        pattern: Regex pattern with capture groups.
        group: Which capture group to return.
        default: Value if no match.

    Returns:
        Matched string or default.
    """
    match = re.search(pattern, content)
    if match and len(match.groups()) >= group:
        return match.group(group)
    return default
