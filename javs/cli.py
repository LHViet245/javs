"""CLI interface for javs using Typer.

Replaces Javinizer's complex single-function CmdletBinding with clean subcommands.
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from javs import __version__

app = typer.Typer(
    name="javs",
    help="🎬 A powerful CLI tool to scrape, organize, and manage JAV media libraries.",
    add_completion=True,
)
console = Console()

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
            "[yellow]Javlibrary is blocked by Cloudflare, or cf_clearance has expired.[/yellow]"
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


def _build_find_facade(cfg, config_path: Path):
    from javs.application import PlatformFacade
    from javs.core.engine import JavsEngine
    from javs.database.connection import open_database, resolve_database_path
    from javs.database.migrations import initialize_database
    from javs.database.repositories.events import JobEventsRepository
    from javs.database.repositories.jobs import JobsRepository
    from javs.jobs import PlatformJobRunner

    db_path = resolve_database_path(cfg)
    initialize_database(db_path)
    connection = open_database(db_path)
    jobs = JobsRepository(connection)
    events = JobEventsRepository(connection)
    facade = PlatformFacade(
        jobs=jobs,
        events=events,
        runner=PlatformJobRunner(jobs=jobs, events=events),
        find_engine_factory=lambda: JavsEngine(
            cfg,
            cloudflare_recovery_handler=_build_javlibrary_recovery_handler(cfg, config_path),
        ),
    )
    return facade, connection.close


def _print_run_diagnostics(engine) -> None:
    """Render compact warnings collected during the last engine run."""
    diagnostics = getattr(engine, "last_run_diagnostics", [])
    if not diagnostics:
        return

    console.print("[yellow]Warnings:[/yellow]")
    printed_hints: set[str] = set()
    for item in diagnostics:
        scraper = item.get("scraper", "unknown")
        kind = item.get("kind", "")
        message = _DIAGNOSTIC_MESSAGES.get(kind, kind.replace("_", " "))
        console.print(f"- {scraper}: {message}")
        detail = item.get("detail")
        if detail:
            console.print(f"  {detail}")
        hint = _DIAGNOSTIC_HINTS.get(kind)
        if hint and hint not in printed_hints:
            console.print(f"  {escape(hint)}")
            printed_hints.add(hint)


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
    cleanup_empty_source_dir: bool | None = typer.Option(
        None,
        "--cleanup-empty-source-dir/--no-cleanup-empty-source-dir",
        help="Remove empty source directories after a successful sort.",
    ),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """📂 Scan, scrape, and sort video files into an organized library."""
    from javs.config import load_config
    from javs.core.engine import JavsEngine

    cfg = load_config(config_path)
    effective_cleanup_empty_source_dir = (
        cleanup_empty_source_dir
        if cleanup_empty_source_dir is not None
        else cfg.sort.cleanup_empty_source_dir
    )
    engine = JavsEngine(cfg, cloudflare_recovery_handler=_build_javlibrary_recovery_handler(
        cfg, _resolve_config_path(config_path)
    ))

    with _status_context("[bold green]Sorting files..."):
        results = asyncio.run(
            engine.sort_path(
                source,
                dest,
                recurse,
                force,
                preview,
                cleanup_empty_source_dir=effective_cleanup_empty_source_dir,
            )
        )

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
    from javs.application import FindMovieRequest
    from javs.config import load_config

    cfg = load_config(config_path)
    resolved_config_path = _resolve_config_path(config_path)
    facade, cleanup = _build_find_facade(cfg, resolved_config_path)
    scraper_list = scrapers.split(",") if scrapers else None

    try:
        with _status_context("[bold cyan]Searching..."):
            response = asyncio.run(
                facade.find_movie(
                    FindMovieRequest(movie_id=movie_id, scraper_names=scraper_list),
                    origin="cli",
                )
            )
    finally:
        cleanup()

    data = response.result

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

    _print_run_diagnostics(facade)


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
                "[red]Javlibrary credentials are incomplete. "
                "Both cf_clearance and browser_user_agent are required.[/red]"
            )
            raise typer.Exit(1)
        try:
            asyncio.run(validate_javlibrary_credentials(cfg, credentials))
        except Exception as exc:
            console.print(f"[red]Javlibrary credential test failed:[/red] {exc}")
            if isinstance(exc, CloudflareBlockedError) and exc.guidance:
                print_cloudflare_guidance(exc)
            raise typer.Exit(1) from exc
        console.print("[green]Javlibrary credentials are valid.[/green]")

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
    """Render movie data with a compact hero-and-details layout."""

    def shorten_url(url: str, limit: int = 72) -> str:
        if len(url) <= limit:
            return url
        return f"{url[:limit - 3]}..."

    field_sources = data.field_sources or {}

    def with_source(value: str, field_name: str | None = None) -> Text:
        text = Text(value)
        if field_name:
            source = field_sources.get(field_name)
            if source:
                text.append(f" [{source}]", style="dim")
        return text

    def add_pair_row(
        table: Table,
        left: tuple[str, str, str] | None,
        right: tuple[str, str, str] | None = None,
    ) -> None:
        row: list[Text] = []
        if left:
            row.extend([Text(left[0], style="bold cyan"), with_source(left[1], left[2])])
        else:
            row.extend([Text(""), Text("")])
        if right:
            row.extend([Text(right[0], style="bold cyan"), with_source(right[1], right[2])])
        else:
            row.extend([Text(""), Text("")])
        table.add_row(*row)

    meta = Table.grid(expand=True, padding=(0, 1))
    meta.add_column(style="bold cyan", no_wrap=True)
    meta.add_column(ratio=1)
    meta.add_column(style="bold cyan", no_wrap=True)
    meta.add_column(justify="right", ratio=1)
    meta.add_row(
        Text("ID", style="bold cyan"),
        with_source(data.id, "id"),
        Text("Source", style="bold cyan"),
        Text(data.source or "-", style="dim"),
    )

    hero = Table.grid(expand=True, padding=(0, 0))
    hero.add_column(ratio=1)
    title_text = with_source(data.title or data.id, "title")
    title_text.stylize("bold")
    hero.add_row(title_text)
    if data.alternate_title:
        original_title = Text("Original: ", style="dim")
        original_title.append_text(with_source(data.alternate_title, "alternate_title"))
        original_title.stylize("dim", 0, len("Original: "))
        hero.add_row(original_title)

    details = Table.grid(expand=True, padding=(0, 2))
    details.add_column(style="bold cyan", no_wrap=True)
    details.add_column(ratio=1, overflow="fold")
    details.add_column(style="bold cyan", no_wrap=True)
    details.add_column(ratio=1, overflow="fold")

    rating_text = None
    if data.rating:
        rating_text = (
            f"{data.rating.rating}/10 ({data.rating.votes} votes)"
            if data.rating.votes is not None
            else f"{data.rating.rating}/10"
        )

    actress_names = None
    if data.actresses:
        actress_names = ", ".join(actress.full_name for actress in data.actresses)

    pair_rows = [
        (("Studio", data.maker, "maker") if data.maker else None,
         ("Label", data.label, "label") if data.label else None),
        (("Release Date", data.release_date.isoformat(), "release_date")
         if data.release_date
         else None,
         None),
        (("Runtime", f"{data.runtime} min", "runtime") if data.runtime else None,
         ("Rating", rating_text, "rating") if rating_text else None),
        (("Director", data.director, "director") if data.director else None,
         ("Actresses", actress_names, "actresses") if actress_names else None),
    ]
    for left, right in pair_rows:
        if left or right:
            add_pair_row(details, left, right)

    long_rows = Table.grid(expand=True, padding=(0, 2))
    long_rows.add_column(style="bold cyan", no_wrap=True)
    long_rows.add_column(ratio=1, overflow="fold")
    if data.genres:
        long_rows.add_row(
            Text("Genres", style="bold cyan"),
            with_source(", ".join(data.genres), "genres"),
        )
    if data.series:
        long_rows.add_row(
            Text("Series", style="bold cyan"),
            with_source(data.series, "series"),
        )
    if data.cover_url:
        long_rows.add_row(
            Text("Cover", style="bold cyan"), with_source(shorten_url(data.cover_url), "cover_url")
        )
    if data.trailer_url:
        long_rows.add_row(
            Text("Trailer", style="bold cyan"),
            with_source(shorten_url(data.trailer_url), "trailer_url"),
        )
    if data.screenshot_urls:
        long_rows.add_row(
            Text("Screenshots", style="bold cyan"),
            with_source(str(len(data.screenshot_urls)), "screenshot_urls"),
        )

    renderables: list[object] = [meta, Text(""), hero]
    if details.rows:
        renderables.append(Text(""))
        renderables.append(details)
    if long_rows.rows:
        renderables.append(Text(""))
        renderables.append(long_rows)
    if data.description:
        description_label = Text("Description", style="bold cyan")
        description_value = with_source(data.description, "description")
        description = Table.grid(expand=True)
        description.add_column(ratio=1, overflow="fold")
        description.add_row(description_label)
        description.add_row(description_value)
        renderables.append(Text(""))
        renderables.append(description)

    console.print(Panel(Group(*renderables), title=f"Find Result · {data.id}", border_style="cyan"))


if __name__ == "__main__":
    app()
