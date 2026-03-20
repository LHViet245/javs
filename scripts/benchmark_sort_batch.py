"""Synthetic benchmark for the sort_path orchestration pipeline.

Measures batch processing overhead without hitting live scrapers or file moves.
The benchmark keeps the engine's concurrency and sleep behavior intact while
mocking scanner/find/organizer work with controlled async delays.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import javs.core.engine as engine_module
from javs.config.models import JavsConfig
from javs.core.engine import JavsEngine
from javs.models.file import ScannedFile
from javs.models.movie import MovieData


@dataclass
class BenchmarkResult:
    files: int
    throttle_limit: int
    sleep: float
    scrape_delay: float
    organize_delay: float
    elapsed_seconds: float
    files_per_second: float
    processed: int


def _build_scanned_files(root: Path, count: int) -> list[ScannedFile]:
    files: list[ScannedFile] = []
    for idx in range(1, count + 1):
        movie_id = f"ABP-{idx:03d}"
        file_path = root / f"{movie_id}.mp4"
        file_path.write_bytes(b"0")
        files.append(
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
    return files


async def _run_once(
    *,
    files: int,
    throttle_limit: int,
    sleep: float,
    scrape_delay: float,
    organize_delay: float,
) -> BenchmarkResult:
    config = JavsConfig(throttle_limit=throttle_limit, sleep=int(sleep))

    engine_module.setup_logging = lambda **kwargs: None
    engine_module.ScraperRegistry.load_all = lambda: None
    engine = JavsEngine(config)

    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        source = root / "source"
        dest = root / "dest"
        source.mkdir()
        dest.mkdir()
        scanned_files = _build_scanned_files(source, files)

        engine.scanner.scan = lambda *_args, **_kwargs: scanned_files  # type: ignore[method-assign]

        async def fake_find(
            movie_id: str,
            scraper_names: list[str] | None = None,
            aggregate: bool = True,
        ) -> MovieData:
            del scraper_names, aggregate
            await asyncio.sleep(scrape_delay)
            return MovieData(
                id=movie_id,
                title=f"{movie_id} title",
                maker="Studio",
                cover_url="https://example.com/cover.jpg",
                genres=["Drama"],
                release_date=date(2024, 1, 1),
                source="benchmark",
            )

        async def fake_sort_movie(
            file: ScannedFile,
            data: MovieData,
            dest_root: Path,
            force: bool = False,
            preview: bool = False,
        ) -> None:
            del file, data, dest_root, force, preview
            await asyncio.sleep(organize_delay)

        engine.find = fake_find  # type: ignore[method-assign]
        engine.organizer.sort_movie = fake_sort_movie  # type: ignore[method-assign]

        started = time.perf_counter()
        processed = await engine.sort_path(source, dest, recurse=False, preview=True)
        elapsed = time.perf_counter() - started

    return BenchmarkResult(
        files=files,
        throttle_limit=throttle_limit,
        sleep=sleep,
        scrape_delay=scrape_delay,
        organize_delay=organize_delay,
        elapsed_seconds=round(elapsed, 4),
        files_per_second=round((len(processed) / elapsed) if elapsed else 0.0, 2),
        processed=len(processed),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, default=8, help="Number of synthetic files.")
    parser.add_argument(
        "--throttle-limit",
        type=int,
        default=4,
        help="Engine throttle_limit to benchmark.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Engine sleep setting to benchmark.",
    )
    parser.add_argument(
        "--scrape-delay",
        type=float,
        default=0.05,
        help="Synthetic async delay per fake scrape.",
    )
    parser.add_argument(
        "--organize-delay",
        type=float,
        default=0.01,
        help="Synthetic async delay per fake organize step.",
    )
    parser.add_argument(
        "--compare-zero-sleep",
        action="store_true",
        help="Also benchmark the same batch with sleep forced to 0.",
    )
    return parser


def _print_result(label: str, result: BenchmarkResult) -> None:
    payload = {"label": label, **asdict(result)}
    print(json.dumps(payload, indent=2))


async def _main() -> int:
    args = _build_parser().parse_args()

    baseline = await _run_once(
        files=args.files,
        throttle_limit=args.throttle_limit,
        sleep=args.sleep,
        scrape_delay=args.scrape_delay,
        organize_delay=args.organize_delay,
    )
    _print_result("configured", baseline)

    if args.compare_zero_sleep:
        zero_sleep = await _run_once(
            files=args.files,
            throttle_limit=args.throttle_limit,
            sleep=0,
            scrape_delay=args.scrape_delay,
            organize_delay=args.organize_delay,
        )
        _print_result("zero_sleep", zero_sleep)

        if zero_sleep.elapsed_seconds:
            slowdown = round(baseline.elapsed_seconds / zero_sleep.elapsed_seconds, 2)
            print(
                json.dumps(
                    {
                        "label": "delta",
                        "extra_seconds": round(
                            baseline.elapsed_seconds - zero_sleep.elapsed_seconds,
                            4,
                        ),
                        "slowdown_factor": slowdown,
                    },
                    indent=2,
                )
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
