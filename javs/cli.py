"""CLI interface for javs using Typer.

Replaces Javinizer's complex single-function CmdletBinding with clean subcommands.
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from javs import __version__

app = typer.Typer(
    name="javs",
    help="🎬 A powerful CLI tool to scrape, organize, and manage JAV media libraries.",
    add_completion=True,
)
console = Console()

_PROVENANCE_FIELD_ORDER = (
    "title",
    "description",
    "maker",
    "release_date",
    "runtime",
    "rating",
    "genres",
    "actresses",
    "director",
    "cover_url",
    "trailer_url",
    "screenshot_urls",
)


_DIAGNOSTIC_MESSAGES = {
    "proxy_auth_failed": "proxy auth failed",
    "proxy_unreachable": "proxy unreachable",
    "cloudflare_blocked": "Cloudflare blocked",
    "translation_provider_unavailable": "translation provider unavailable",
    "translation_config_invalid": "translation config invalid",
}

_DIAGNOSTIC_HINTS = {
    "proxy_auth_failed": "Next: run `javs config proxy-test`.",
    "proxy_unreachable": "Next: run `javs config proxy-test`.",
    "cloudflare_blocked": "Next: run `javs config javlibrary-cookie`.",
    "translation_provider_unavailable": (
        "Next: install translation extras with `./venv/bin/pip install -e \".[translate]\"`."
    ),
    "translation_config_invalid": "Next: update `sort.metadata.nfo.translate` in your config.",
}


def _resolve_config_path(config_path: Path | None) -> Path:
    from javs.config.loader import get_default_config_path

    return config_path or get_default_config_path()


def _build_javlibrary_recovery_handler(cfg, config_path: Path):
    from javs.services.javlibrary_auth import (
        configure_javlibrary_credentials,
        is_interactive_terminal,
    )

    async def recover(_error) -> object | None:
        if not is_interactive_terminal():
            return None
        console.print(
            "[yellow]Javlibrary đang bị Cloudflare block hoặc cf_clearance đã hết hạn.[/yellow]"
        )
        return await configure_javlibrary_credentials(
            cfg,
            config_path,
            prompt_on_missing=True,
            send_notification=True,
            save_on_success=True,
        )

    return recover


def _status_context(message: str):
    from javs.services.javlibrary_auth import is_interactive_terminal

    if is_interactive_terminal():
        return nullcontext()
    return console.status(message, spinner="dots")


def _print_run_diagnostics(engine) -> None:
    """Render compact warnings collected during the last engine run."""
    diagnostics = getattr(engine, "last_run_diagnostics", [])
    if not diagnostics:
        return

    console.print("[yellow]Warnings:[/yellow]")
    for item in diagnostics:
        scraper = item.get("scraper", "unknown")
        kind = item.get("kind", "")
        message = _DIAGNOSTIC_MESSAGES.get(kind, kind.replace("_", " "))
        console.print(f"- {scraper}: {message}")
        detail = item.get("detail")
        if detail:
            console.print(f"  {detail}")
        hint = _DIAGNOSTIC_HINTS.get(kind)
        if hint:
            console.print(f"  {escape(hint)}")


def _print_run_summary(engine) -> None:
    """Render a compact batch summary for sort/update commands."""
    summary = getattr(engine, "last_run_summary", None)
    if not summary:
        return

    warning_label = "warning" if summary["warnings"] == 1 else "warnings"
    console.print(
        "[bold]Summary:[/bold] "
        f"{summary['total']} scanned, "
        f"{summary['processed']} processed, "
        f"{summary['skipped']} skipped, "
        f"{summary['failed']} failed, "
        f"{summary['warnings']} {warning_label}"
    )


def _print_preview_plan(engine) -> None:
    """Render planned preview actions for sort/update dry runs."""
    preview_plan = getattr(engine, "last_preview_plan", [])
    if not preview_plan:
        return

    table = Table(title="Preview Plan")
    table.add_column("Source", style="cyan", overflow="fold")
    table.add_column("ID", style="white")
    table.add_column("Target", style="green", overflow="fold")

    for item in preview_plan:
        table.add_row(item["source"], item["id"], item["target"])

    console.print(table)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"javs v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """javs — organize your JAV library with ease."""


@app.command()
def sort(
    source: Path = typer.Argument(..., help="Source directory or file path."),
    dest: Path = typer.Argument(..., help="Destination root directory."),
    recurse: bool = typer.Option(False, "--recurse", "-r", help="Scan subdirectories."),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files."),
    preview: bool = typer.Option(False, "--preview", "-p", help="Dry run: show what would happen."),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """📂 Scan, scrape, and sort video files into an organized library."""
    from javs.config import load_config
    from javs.core.engine import JavsEngine

    cfg = load_config(config_path)
    engine = JavsEngine(cfg, cloudflare_recovery_handler=_build_javlibrary_recovery_handler(
        cfg, _resolve_config_path(config_path)
    ))

    with _status_context("[bold green]Sorting files..."):
        results = asyncio.run(engine.sort_path(source, dest, recurse, force, preview))

    if results:
        table = Table(title=f"✅ Sorted {len(results)} files")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Studio", style="green")

        for data in results:
            table.add_row(data.id, data.title or "—", data.maker or "—")

        console.print(table)
    else:
        console.print("[yellow]No files were processed.[/yellow]")

    if preview:
        _print_preview_plan(engine)
    _print_run_summary(engine)
    _print_run_diagnostics(engine)


@app.command("update")
def update(
    source: Path = typer.Argument(..., help="Sorted library root or a single video file."),
    recurse: bool = typer.Option(False, "--recurse", "-r", help="Scan subdirectories."),
    scrapers: str | None = typer.Option(
        None, "--scrapers", "-s", help="Comma-separated scraper names to use."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing sidecars and downloads during update.",
    ),
    refresh_images: bool = typer.Option(
        False,
        "--refresh-images",
        help="Re-download existing cover, poster, actress, and screenshot images.",
    ),
    refresh_trailer: bool = typer.Option(
        False,
        "--refresh-trailer",
        help="Re-download existing trailer files when metadata has a trailer URL.",
    ),
    preview: bool = typer.Option(False, "--preview", "-p", help="Dry run: show what would happen."),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """♻️ Refresh metadata sidecars for an already-sorted library without moving files."""
    from javs.config import load_config
    from javs.core.engine import JavsEngine

    cfg = load_config(config_path)
    engine = JavsEngine(
        cfg,
        cloudflare_recovery_handler=_build_javlibrary_recovery_handler(
            cfg, _resolve_config_path(config_path)
        ),
    )
    scraper_list = scrapers.split(",") if scrapers else None

    with _status_context("[bold green]Updating sorted library..."):
        results = asyncio.run(
            engine.update_path(
                source,
                recurse=recurse,
                force=force,
                preview=preview,
                scraper_names=scraper_list,
                refresh_images=refresh_images,
                refresh_trailer=refresh_trailer,
            )
        )

    if results:
        table = Table(title=f"♻️ Updated {len(results)} files")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Studio", style="green")

        for data in results:
            table.add_row(data.id, data.title or "—", data.maker or "—")

        console.print(table)
    else:
        console.print("[yellow]No files were updated.[/yellow]")

    if preview:
        _print_preview_plan(engine)
    _print_run_summary(engine)
    _print_run_diagnostics(engine)


@app.command()
def find(
    movie_id: str = typer.Argument(..., help="JAV movie ID (e.g., ABP-420)."),
    scrapers: str | None = typer.Option(
        None, "--scrapers", "-s", help="Comma-separated scraper names to use."
    ),
    nfo: bool = typer.Option(False, "--nfo", help="Output NFO XML."),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON."),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """🔍 Look up metadata for a movie ID."""
    from javs.config import load_config
    from javs.core.engine import JavsEngine

    cfg = load_config(config_path)
    engine = JavsEngine(cfg, cloudflare_recovery_handler=_build_javlibrary_recovery_handler(
        cfg, _resolve_config_path(config_path)
    ))

    scraper_list = scrapers.split(",") if scrapers else None

    with _status_context("[bold cyan]Searching..."):
        data = asyncio.run(engine.find_one(movie_id, scraper_names=scraper_list))

    if not data:
        console.print(f"[red]No results found for {movie_id}[/red]")
        raise typer.Exit(1)

    if nfo:
        from javs.core.nfo import NfoGenerator

        nfo_gen = NfoGenerator(cfg.sort.metadata.nfo)
        console.print(nfo_gen.generate(data))
    elif json_output:
        console.print(data.model_dump_json(indent=2))
    else:
        _display_movie_data(data)

    _print_run_diagnostics(engine)


@app.command()
def config(
    action: str = typer.Argument(
        "show",
        help=(
            "Action: show, edit, create, path, sync, csv-paths, "
            "init-csv, javlibrary-cookie, javlibrary-test, proxy-test."
        ),
    ),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """⚙️ Manage configuration."""
    from javs.config import create_default_config, load_config
    from javs.services.http import CloudflareBlockedError
    from javs.services.javlibrary_auth import (
        configure_javlibrary_credentials,
        print_cloudflare_guidance,
        validate_javlibrary_credentials,
    )
    from javs.services.proxy_diagnostics import run_proxy_diagnostics

    path = _resolve_config_path(config_path)

    if action == "show":
        from javs.config import redact_config_for_display

        cfg = load_config(path)
        console.print_json(data=redact_config_for_display(cfg))

    elif action == "create":
        create_default_config(path)
        console.print(f"[green]Config created at {path}[/green]")

    elif action == "path":
        console.print(str(path))

    elif action == "edit":
        import os
        import subprocess

        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
        if not path.exists():
            create_default_config(path)
        subprocess.run([editor, str(path)])

    elif action == "sync":
        from javs.config.updater import sync_user_config
        console.print("[yellow]Syncing configuration setup with default template...[/yellow]")
        success = sync_user_config(config_path=path)
        if success:
            console.print(
                f"[green]Successfully synced and upgraded local config file at {path}[/green]"
            )
        else:
            console.print("[red]Failed to sync configuration. Check logs for details.[/red]")
            raise typer.Exit(1)

    elif action == "csv-paths":
        from javs.config.csv_templates import get_effective_csv_paths

        cfg = load_config(path)
        csv_paths = get_effective_csv_paths(cfg, path)
        console.print("[bold]CSV Paths[/bold]")
        for filename, csv_path in csv_paths.items():
            exists = "yes" if csv_path.exists() else "no"
            console.print(f"{filename}: {csv_path} (exists: {exists})", soft_wrap=True)

    elif action == "init-csv":
        from javs.config.csv_templates import init_csv_templates

        cfg = load_config(path)
        result = init_csv_templates(cfg, path)
        for created in result.created:
            console.print(f"[green]Created CSV template:[/green] {created}", soft_wrap=True)
        for existing in result.existing:
            console.print(f"[yellow]CSV already exists:[/yellow] {existing}", soft_wrap=True)
        console.print(f"[cyan]genres.csv:[/cyan] {result.genre_csv_path}", soft_wrap=True)
        console.print(f"[cyan]thumbs.csv:[/cyan] {result.thumb_csv_path}", soft_wrap=True)

    elif action == "javlibrary-cookie":
        cfg = load_config(path)
        credentials = asyncio.run(
            configure_javlibrary_credentials(
                cfg,
                path,
                prompt_on_missing=False,
                send_notification=False,
                save_on_success=True,
            )
        )
        if credentials is None:
            raise typer.Exit(1)

    elif action == "javlibrary-test":
        from javs.services.javlibrary_auth import JavlibraryCredentials

        cfg = load_config(path)
        credentials = JavlibraryCredentials(
            cf_clearance=cfg.javlibrary.cookie_cf_clearance.strip(),
            browser_user_agent=cfg.javlibrary.browser_user_agent.strip(),
        )
        if not credentials.cf_clearance or not credentials.browser_user_agent:
            console.print(
                "[red]Javlibrary credential chưa đầy đủ. "
                "Cần cf_clearance và browser_user_agent.[/red]"
            )
            raise typer.Exit(1)
        try:
            asyncio.run(validate_javlibrary_credentials(cfg, credentials))
        except Exception as exc:
            console.print(f"[red]Javlibrary credential test thất bại:[/red] {exc}")
            if isinstance(exc, CloudflareBlockedError) and exc.guidance:
                print_cloudflare_guidance(exc)
            raise typer.Exit(1) from exc
        console.print("[green]Javlibrary credential hợp lệ.[/green]")

    elif action == "proxy-test":
        cfg = load_config(path)
        result = asyncio.run(run_proxy_diagnostics(cfg))
        if result.ok:
            console.print(f"[green]{result.message}[/green]")
            return

        console.print(f"[red]{result.message}[/red]")
        if result.detail:
            console.print(result.detail)
        raise typer.Exit(1)

    else:
        console.print(f"[red]Unknown action: {action}[/red]")


@app.command()
def scrapers() -> None:
    """📋 List all available scrapers."""
    from javs.scrapers.registry import ScraperRegistry

    ScraperRegistry.load_all()
    names = ScraperRegistry.list_names()

    table = Table(title="Available Scrapers")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")

    for name in sorted(names):
        table.add_row(name, "✅ registered")

    console.print(table)


def _display_movie_data(data) -> None:
    """Render movie data as a sectioned inspector view."""

    def add_row(rows: list[tuple[str, str]], label: str, value: object) -> None:
        if value in (None, "", [], {}):
            return
        rows.append((label, str(value)))

    def make_section(title: str, rows: list[tuple[str, str]]) -> Panel | None:
        if not rows:
            return None
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(style="bold cyan", no_wrap=True)
        grid.add_column(overflow="fold")
        for label, value in rows:
            grid.add_row(label, value)
        return Panel(grid, title=title, border_style="cyan")

    def shorten_url(url: str, limit: int = 72) -> str:
        if len(url) <= limit:
            return url
        return f"{url[:limit - 3]}..."

    def shorten_text(text: str, limit: int = 200) -> str:
        if len(text) <= limit:
            return text
        return f"{text[:limit - 3].rstrip()}..."

    sections: list[Panel] = []

    identity_rows: list[tuple[str, str]] = []
    add_row(identity_rows, "ID", data.id)
    add_row(identity_rows, "Title", data.title)
    add_row(identity_rows, "Original Title", data.alternate_title)
    add_row(identity_rows, "Primary Source", data.source)
    identity_section = make_section("Identity", identity_rows)
    if identity_section is not None:
        sections.append(identity_section)

    release_rows: list[tuple[str, str]] = []
    add_row(release_rows, "Studio", data.maker)
    add_row(release_rows, "Label", data.label)
    add_row(release_rows, "Series", data.series)
    if data.release_date:
        add_row(release_rows, "Release Date", data.release_date.isoformat())
    if data.runtime:
        add_row(release_rows, "Runtime", f"{data.runtime} min")
    if data.rating:
        rating_text = (
            f"{data.rating.rating}/10 ({data.rating.votes} votes)"
            if data.rating.votes is not None
            else f"{data.rating.rating}/10"
        )
        add_row(release_rows, "Rating", rating_text)
    release_section = make_section("Release", release_rows)
    if release_section is not None:
        sections.append(release_section)

    people_rows: list[tuple[str, str]] = []
    if data.actresses:
        actress_names = ", ".join(actress.full_name for actress in data.actresses)
        add_row(people_rows, "Actresses", actress_names)
    add_row(people_rows, "Director", data.director)
    people_section = make_section("People", people_rows)
    if people_section is not None:
        sections.append(people_section)

    content_rows: list[tuple[str, str]] = []
    if data.genres:
        add_row(content_rows, "Genres", ", ".join(data.genres))
    if data.description:
        add_row(content_rows, "Description", shorten_text(data.description))
    content_section = make_section("Content", content_rows)
    if content_section is not None:
        sections.append(content_section)

    asset_rows: list[tuple[str, str]] = []
    if data.cover_url:
        add_row(asset_rows, "Cover URL", shorten_url(data.cover_url))
    if data.trailer_url:
        add_row(asset_rows, "Trailer URL", shorten_url(data.trailer_url))
    if data.screenshot_urls:
        add_row(asset_rows, "Screenshot Count", len(data.screenshot_urls))
    assets_section = make_section("Assets", asset_rows)
    if assets_section is not None:
        sections.append(assets_section)

    provenance_rows: list[tuple[str, str]] = []
    field_sources = data.field_sources or {}
    ordered_fields = [field for field in _PROVENANCE_FIELD_ORDER if field in field_sources]
    extra_fields = sorted(field for field in field_sources if field not in _PROVENANCE_FIELD_ORDER)
    for field_name in ordered_fields + extra_fields:
        add_row(provenance_rows, field_name, field_sources[field_name])
    provenance_section = make_section("Field Provenance", provenance_rows)
    if provenance_section is not None:
        sections.append(provenance_section)

    for section in sections:
        console.print(section)


if __name__ == "__main__":
    app()
