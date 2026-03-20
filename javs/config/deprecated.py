"""Helpers for deprecated config keys that should be phased out safely."""

from __future__ import annotations

DEPRECATED_CONFIG_PATHS: tuple[tuple[str, ...], ...] = (
    ("javlibrary", "cookie_cf_bm"),
    ("javlibrary", "cookie_session"),
    ("javlibrary", "cookie_userid"),
    ("sort", "rename_folder_in_place"),
    ("sort", "format", "output_folder"),
    ("sort", "format", "group_actress"),
    ("sort", "metadata", "tag_csv"),
    ("scrapers", "options"),
    ("locations", "uncensor_csv"),
    ("locations", "history_csv"),
    ("locations", "tag_csv"),
    ("javdb",),
    ("check_updates",),
)


def find_deprecated_config_paths(
    data: dict,
    prefix: tuple[str, ...] = (),
) -> list[str]:
    """Return dotted paths for deprecated config keys present in a config tree."""
    found: list[str] = []

    for key, value in data.items():
        current = prefix + (str(key),)
        if current in DEPRECATED_CONFIG_PATHS:
            found.append(".".join(current))
        elif isinstance(value, dict):
            found.extend(find_deprecated_config_paths(value, current))

    return found


def prune_deprecated_config_paths(
    data: dict,
    prefix: tuple[str, ...] = (),
) -> list[str]:
    """Remove deprecated config keys from a config tree and return their dotted paths."""
    removed: list[str] = []

    for key in list(data.keys()):
        value = data[key]
        current = prefix + (str(key),)
        if current in DEPRECATED_CONFIG_PATHS:
            data.pop(key, None)
            removed.append(".".join(current))
        elif isinstance(value, dict):
            removed.extend(prune_deprecated_config_paths(value, current))

    return removed
