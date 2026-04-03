"""Parser and config helpers for the manual real scrape benchmark script."""

from __future__ import annotations

from datetime import date

from javs.config.models import JavsConfig
from javs.models.movie import MovieData
from scripts.benchmark_real_scrape import (
    DEFAULT_IDS,
    _apply_overrides,
    _find_sort_result_for_movie_id,
    parse_csv_arg,
)


def test_parse_csv_arg_trims_and_filters_empty_values() -> None:
    assert parse_csv_arg(" dmm, r18dev, , javlibrary ") == ["dmm", "r18dev", "javlibrary"]


def test_parse_csv_arg_none_returns_none() -> None:
    assert parse_csv_arg(None) is None


def test_apply_overrides_updates_selected_scrapers_without_mutating_source() -> None:
    base = JavsConfig()
    overridden = _apply_overrides(
        base,
        sleep_override=0,
        throttle_limit_override=4,
        scrapers=["dmm", "javlibrary"],
    )

    assert overridden.sleep == 0
    assert overridden.throttle_limit == 4
    assert overridden.scrapers.enabled["dmm"] is True
    assert overridden.scrapers.enabled["javlibrary"] is True
    assert overridden.scrapers.enabled["r18dev"] is False
    assert overridden.scrapers.use_proxy["dmm"] is True
    assert overridden.scrapers.use_proxy["javlibrary"] is False
    assert base.sleep == 2
    assert base.throttle_limit == 1


def test_default_ids_remain_stable() -> None:
    assert DEFAULT_IDS == ["ABP-420", "SSIS-001", "START-539", "FSDSS-198"]


def test_find_sort_result_prefers_original_filename_match() -> None:
    results = [
        MovieData(
            id="ABP-420DOD",
            title="Movie",
            release_date=date(2024, 1, 1),
            source="dmm",
            original_filename="ABP-420.mp4",
        ),
        MovieData(
            id="SSIS-001",
            title="Movie",
            release_date=date(2024, 1, 1),
            source="dmm",
            original_filename="SSIS-001.mp4",
        ),
    ]

    result = _find_sort_result_for_movie_id(results, "ABP-420")

    assert result is not None
    assert result.id == "ABP-420DOD"


def test_find_sort_result_falls_back_to_exact_movie_id() -> None:
    results = [
        MovieData(
            id="START-539",
            title="Movie",
            release_date=date(2024, 1, 1),
            source="dmm",
        )
    ]

    result = _find_sort_result_for_movie_id(results, "START-539")

    assert result is not None
    assert result.id == "START-539"
