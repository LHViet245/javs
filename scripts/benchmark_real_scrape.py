"""Manual-only benchmark for real scrape latency and batch orchestration.

This script is intentionally excluded from automated CI workflows. It is
designed for local, manual runs against live scrapers so we can compare:

- per-ID scrape latency
- batch `sort_path()` throughput under different `sleep` values
- request counts and request timings across `get()`, `get_json()`, `get_cf()`,
  and `download()`

Use `--mode find` to benchmark direct metadata lookup and `--mode sort` to
benchmark the end-to-end batch pipeline in preview mode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from javs.config import JavsConfig, load_config
from javs.core.engine import JavsEngine
from javs.models.file import ScannedFile
from javs.models.movie import MovieData

DEFAULT_IDS = ["ABP-420", "SSIS-001", "START-539", "FSDSS-198"]
DEFAULT_SCRAPERS = ["dmm", "r18dev", "javlibrary", "mgstageja"]
REQUEST_METHODS = ("get", "get_json", "get_cf", "download")
_GET_CF_DEPTH: ContextVar[int] = ContextVar("get_cf_depth", default=0)


@dataclass(slots=True)
class RequestMetric:
    method: str
    url: str
    elapsed_seconds: float
    use_proxy: bool
    ok: bool
    error: str | None = None


@dataclass(slots=True)
class ItemMetric:
    mode: str
    index: int
    movie_id: str
    elapsed_seconds: float
    status: str
    scraper_names: list[str] = field(default_factory=list)
    source: str | None = None
    result_count: int | None = None
    error: str | None = None


@dataclass(slots=True)
class RunMetric:
    repeat: int
    elapsed_seconds: float
    items: list[ItemMetric] = field(default_factory=list)
    requests: list[RequestMetric] = field(default_factory=list)


def parse_csv_arg(value: str | None) -> list[str] | None:
    """Parse a comma-separated CLI argument into a cleaned list."""
    if value is None:
        return None

    items = [part.strip() for part in value.split(",")]
    cleaned = [item for item in items if item]
    return cleaned


def positive_int(value: str) -> int:
    """Argparse validator for positive integers."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return parsed


def _format_ids(ids: list[str]) -> str:
    return ", ".join(ids)


def _selected_scrapers(config: JavsConfig, scrapers: list[str] | None) -> list[str]:
    if scrapers:
        return scrapers
    return [name for name, enabled in config.scrapers.enabled.items() if enabled]


def _apply_overrides(
    base_config: JavsConfig,
    *,
    sleep_override: int | None,
    throttle_limit_override: int | None,
    scrapers: list[str] | None,
) -> JavsConfig:
    config = base_config.model_copy(deep=True)

    if sleep_override is not None:
        config.sleep = sleep_override

    if throttle_limit_override is not None:
        config.throttle_limit = throttle_limit_override

    if scrapers:
        selected = set(scrapers)
        enabled = {name: name in selected for name in config.scrapers.enabled.keys()}
        for name in scrapers:
            enabled.setdefault(name, True)

        use_proxy = {name: config.scrapers.use_proxy.get(name, False) for name in enabled}
        config.scrapers.enabled = enabled
        config.scrapers.use_proxy = use_proxy

    return config


def _build_scanned_files(root: Path, ids: list[str]) -> list[ScannedFile]:
    scanned_files: list[ScannedFile] = []
    for movie_id in ids:
        file_path = root / f"{movie_id}.mp4"
        file_path.write_bytes(b"0")
        scanned_files.append(
            ScannedFile(
                path=file_path,
                filename=file_path.name,
                basename=file_path.stem,
                extension=file_path.suffix,
                directory=root,
                size_bytes=1,
                movie_id=movie_id,
            )
        )
    return scanned_files


def _find_sort_result_for_movie_id(results: list[MovieData], movie_id: str) -> MovieData | None:
    for result in results:
        if result.original_filename and Path(result.original_filename).stem == movie_id:
            return result
    for result in results:
        if result.id == movie_id:
            return result
    return None


def _extract_url(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if "url" in kwargs and isinstance(kwargs["url"], str):
        return kwargs["url"]
    if args and isinstance(args[0], str):
        return args[0]
    return ""


def _extract_use_proxy(kwargs: dict[str, Any]) -> bool:
    return bool(kwargs.get("use_proxy", False))


def _wrap_request_method(
    recorder: list[RequestMetric],
    method_name: str,
    original: Any,
):
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        url = _extract_url(args, kwargs)
        suppress_metric = method_name == "get" and _GET_CF_DEPTH.get() > 0
        try:
            result = await original(*args, **kwargs)
        except Exception as exc:
            if not suppress_metric:
                recorder.append(
                    RequestMetric(
                        method=method_name,
                        url=url,
                        elapsed_seconds=round(time.perf_counter() - started, 4),
                        use_proxy=_extract_use_proxy(kwargs),
                        ok=False,
                        error=type(exc).__name__,
                    )
                )
            raise

        if not suppress_metric:
            recorder.append(
                RequestMetric(
                    method=method_name,
                    url=url,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    use_proxy=_extract_use_proxy(kwargs),
                    ok=True,
                )
            )
        return result

    return wrapper


def _wrap_download_method(
    recorder: list[RequestMetric],
    original: Any,
):
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        url = _extract_url(args, kwargs)
        try:
            result = await original(*args, **kwargs)
        except Exception as exc:
            recorder.append(
                RequestMetric(
                    method="download",
                    url=url,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    use_proxy=_extract_use_proxy(kwargs),
                    ok=False,
                    error=type(exc).__name__,
                )
            )
            raise

        recorder.append(
            RequestMetric(
                method="download",
                url=url,
                elapsed_seconds=round(time.perf_counter() - started, 4),
                use_proxy=_extract_use_proxy(kwargs),
                ok=True,
            )
        )
        return result

    return wrapper


def _wrap_get_cf_method(
    recorder: list[RequestMetric],
    original: Any,
):
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        url = _extract_url(args, kwargs)
        token = _GET_CF_DEPTH.set(_GET_CF_DEPTH.get() + 1)
        try:
            result = await original(*args, **kwargs)
        except Exception as exc:
            recorder.append(
                RequestMetric(
                    method="get_cf",
                    url=url,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    use_proxy=_extract_use_proxy(kwargs),
                    ok=False,
                    error=type(exc).__name__,
                )
            )
            raise
        finally:
            _GET_CF_DEPTH.reset(token)

        recorder.append(
            RequestMetric(
                method="get_cf",
                url=url,
                elapsed_seconds=round(time.perf_counter() - started, 4),
                use_proxy=_extract_use_proxy(kwargs),
                ok=True,
            )
        )
        return result

    return wrapper


def _instrument_http_client(engine: JavsEngine) -> list[RequestMetric]:
    recorder: list[RequestMetric] = []
    engine.http.get = _wrap_request_method(recorder, "get", engine.http.get)  # type: ignore[method-assign]
    engine.http.get_json = _wrap_request_method(  # type: ignore[method-assign]
        recorder, "get_json", engine.http.get_json
    )
    engine.http.get_cf = _wrap_get_cf_method(recorder, engine.http.get_cf)  # type: ignore[method-assign]
    engine.http.download = _wrap_download_method(recorder, engine.http.download)  # type: ignore[method-assign]
    return recorder


def _duration_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "total_seconds": 0.0,
            "mean_seconds": 0.0,
            "median_seconds": 0.0,
            "p95_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
        }

    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(round(len(ordered) * 0.95 + 0.5)) - 1))
    return {
        "count": len(ordered),
        "total_seconds": round(sum(ordered), 4),
        "mean_seconds": round(statistics.mean(ordered), 4),
        "median_seconds": round(statistics.median(ordered), 4),
        "p95_seconds": round(ordered[p95_index], 4),
        "min_seconds": round(min(ordered), 4),
        "max_seconds": round(max(ordered), 4),
    }


def _request_summary(requests: list[RequestMetric]) -> dict[str, Any]:
    grouped: dict[str, list[RequestMetric]] = defaultdict(list)
    for request in requests:
        grouped[request.method].append(request)

    summary: dict[str, Any] = {}
    for method in REQUEST_METHODS:
        subset = grouped.get(method, [])
        summary[method] = {
            **_duration_summary([item.elapsed_seconds for item in subset]),
            "ok": sum(1 for item in subset if item.ok),
            "failed": sum(1 for item in subset if not item.ok),
            "proxy_calls": sum(1 for item in subset if item.use_proxy),
        }

    summary["overall"] = {
        **_duration_summary([item.elapsed_seconds for item in requests]),
        "ok": sum(1 for item in requests if item.ok),
        "failed": sum(1 for item in requests if not item.ok),
    }
    return summary


def _item_summary(items: list[ItemMetric]) -> dict[str, Any]:
    statuses = Counter(item.status for item in items)
    return {
        "count": len(items),
        "status_counts": dict(statuses),
        "elapsed": _duration_summary([item.elapsed_seconds for item in items]),
    }


def _build_payload(
    *,
    mode: str,
    config: JavsConfig,
    config_path: Path | None,
    ids: list[str],
    scrapers: list[str] | None,
    repeat: int,
    runs: list[RunMetric],
) -> dict[str, Any]:
    all_items = [item for run in runs for item in run.items]
    all_requests = [request for run in runs for request in run.requests]

    return {
        "mode": mode,
        "config_path": str(config_path) if config_path else None,
        "ids": ids,
        "scrapers": scrapers,
        "repeat": repeat,
        "sleep": config.sleep,
        "throttle_limit": config.throttle_limit,
        "runs": [asdict(run) for run in runs],
        "summary": {
            "items": _item_summary(all_items),
            "requests": _request_summary(all_requests),
            "run_elapsed": _duration_summary([run.elapsed_seconds for run in runs]),
        },
    }


async def _run_find_once(
    engine: JavsEngine,
    ids: list[str],
    scrapers: list[str] | None,
    repeat_index: int,
) -> RunMetric:
    items: list[ItemMetric] = []
    started = time.perf_counter()

    for index, movie_id in enumerate(ids, start=1):
        item_started = time.perf_counter()
        try:
            data = await engine.find_one(movie_id, scraper_names=scrapers)
        except Exception as exc:
            items.append(
                ItemMetric(
                    mode="find",
                    index=index,
                    movie_id=movie_id,
                    elapsed_seconds=round(time.perf_counter() - item_started, 4),
                    status="error",
                    scraper_names=scrapers or [],
                    error=type(exc).__name__,
                )
            )
            continue

        if data is None:
            items.append(
                ItemMetric(
                    mode="find",
                    index=index,
                    movie_id=movie_id,
                    elapsed_seconds=round(time.perf_counter() - item_started, 4),
                    status="no_result",
                    scraper_names=scrapers or [],
                )
            )
            continue

        items.append(
            ItemMetric(
                mode="find",
                index=index,
                movie_id=movie_id,
                elapsed_seconds=round(time.perf_counter() - item_started, 4),
                status="found",
                scraper_names=scrapers or [],
                source=data.source or None,
            )
        )

    return RunMetric(
        repeat=repeat_index,
        elapsed_seconds=round(time.perf_counter() - started, 4),
        items=items,
        requests=[],
    )


async def _run_sort_once(
    engine: JavsEngine,
    ids: list[str],
    repeat_index: int,
) -> RunMetric:
    items: list[ItemMetric] = []
    started = time.perf_counter()

    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        source = root / "source"
        dest = root / "dest"
        source.mkdir()
        dest.mkdir()
        _build_scanned_files(source, ids)

        try:
            results = await engine.sort_path(source, dest, recurse=False, preview=True)
        except Exception as exc:
            items.append(
                ItemMetric(
                    mode="sort",
                    index=1,
                    movie_id="batch",
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    status="error",
                    error=type(exc).__name__,
                )
            )
            return RunMetric(
                repeat=repeat_index,
                elapsed_seconds=round(time.perf_counter() - started, 4),
                items=items,
                requests=[],
            )

        for index, movie_id in enumerate(ids, start=1):
            result = _find_sort_result_for_movie_id(results, movie_id)
            items.append(
                ItemMetric(
                    mode="sort",
                    index=index,
                    movie_id=movie_id,
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    status="processed" if result else "skipped",
                    source=result.source if result else None,
                )
            )

    return RunMetric(
        repeat=repeat_index,
        elapsed_seconds=round(time.perf_counter() - started, 4),
        items=items,
        requests=[],
    )


async def _execute(mode: str, args: argparse.Namespace) -> dict[str, Any]:
    base_config = load_config(args.config)
    scrapers = _selected_scrapers(base_config, args.scrapers)
    if not args.ids:
        raise ValueError("--ids must contain at least one movie ID")
    if args.scrapers is not None and not args.scrapers:
        raise ValueError("--scrapers must contain at least one scraper name when provided")
    config = _apply_overrides(
        base_config,
        sleep_override=args.sleep_override,
        throttle_limit_override=args.throttle_limit_override,
        scrapers=args.scrapers,
    )

    engine = JavsEngine(config)
    recorder = _instrument_http_client(engine)
    runs: list[RunMetric] = []

    for repeat_index in range(1, args.repeat + 1):
        request_start = len(recorder)
        if mode == "find":
            run = await _run_find_once(
                engine,
                args.ids,
                scrapers if args.scrapers else None,
                repeat_index,
            )
        else:
            run = await _run_sort_once(engine, args.ids, repeat_index)
        run.requests = recorder[request_start:]
        runs.append(run)

    await engine.close()

    return _build_payload(
        mode=mode,
        config=config,
        config_path=args.config,
        ids=args.ids,
        scrapers=scrapers if args.scrapers is not None else None,
        repeat=args.repeat,
        runs=runs,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("find", "sort"),
        required=True,
        help="Benchmark mode: find for direct lookups, sort for preview batch processing.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional config path. Uses the default config lookup if omitted.",
    )
    parser.add_argument(
        "--scrapers",
        type=parse_csv_arg,
        default=DEFAULT_SCRAPERS,
        help="Comma-separated scraper names to benchmark.",
    )
    parser.add_argument(
        "--ids",
        type=parse_csv_arg,
        default=DEFAULT_IDS,
        help="Comma-separated movie IDs to benchmark.",
    )
    parser.add_argument(
        "--repeat",
        type=positive_int,
        default=1,
        help="How many benchmark passes to run.",
    )
    parser.add_argument(
        "--sleep-override",
        type=int,
        default=None,
        help="Override config.sleep for the benchmark run.",
    )
    parser.add_argument(
        "--throttle-limit-override",
        type=int,
        default=None,
        help="Override config.throttle_limit for the benchmark run.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Emit a JSON payload instead of human-readable text.",
    )
    return parser


def _print_human(payload: dict[str, Any]) -> None:
    print(f"Mode: {payload['mode']}")
    print(f"Config sleep: {payload['sleep']}")
    print(f"Throttle limit: {payload['throttle_limit']}")
    print(f"IDs: {_format_ids(payload['ids'])}")
    scrapers = payload["scrapers"] or ["enabled from config"]
    print(f"Scrapers: {_format_ids(scrapers)}")
    print(f"Repeat: {payload['repeat']}")

    for run in payload["runs"]:
        print(f"Run #{run['repeat']}: {run['elapsed_seconds']}s")
        for item in run["items"]:
            source = f" source={item['source']}" if item.get("source") else ""
            error = f" error={item['error']}" if item.get("error") else ""
            print(
                f"  [{item['mode']}] {item['movie_id']} "
                f"{item['status']} in {item['elapsed_seconds']}s{source}{error}"
            )

    request_summary = payload["summary"]["requests"]
    print("Requests:")
    for method in REQUEST_METHODS:
        stats = request_summary[method]
        print(
            f"  {method}: count={stats['count']} "
            f"mean={stats['mean_seconds']}s p95={stats['p95_seconds']}s "
            f"ok={stats['ok']} failed={stats['failed']}"
        )


async def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    payload = await _execute(args.mode, args)
    if args.json_output:
        print(json.dumps(payload, indent=2, default=str))
    else:
        _print_human(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
