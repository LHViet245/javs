"""CLI interface for javs using Typer.

Replaces Javinizer's complex single-function CmdletBinding with clean subcommands.
"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from javs import __version__

app = typer.Typer(
    name="javs",
    help="🎬 A powerful CLI tool to scrape, organize, and manage JAV media libraries.",
    add_completion=True,
)
console = Console()


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


@app.command()
def config(
    action: str = typer.Argument(
        "show",
        help=(
            "Action: show, edit, create, path, sync, csv-paths, "
            "init-csv, javlibrary-cookie, javlibrary-test."
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

    path = _resolve_config_path(config_path)

    if action == "show":
        cfg = load_config(path)
        console.print(cfg.model_dump_json(indent=2))

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
    """Pretty-print movie data to console."""
    from rich.panel import Panel

    lines = []
    lines.append(f"[bold cyan]ID:[/bold cyan] {data.id}")
    if data.title:
        lines.append(f"[bold]Title:[/bold] {data.title}")
    if data.alternate_title:
        lines.append(f"[bold]Alt Title:[/bold] {data.alternate_title}")
    if data.maker:
        lines.append(f"[bold]Studio:[/bold] {data.maker}")
    if data.label:
        lines.append(f"[bold]Label:[/bold] {data.label}")
    if data.series:
        lines.append(f"[bold]Series:[/bold] {data.series}")
    if data.director:
        lines.append(f"[bold]Director:[/bold] {data.director}")
    if data.release_date:
        lines.append(f"[bold]Release:[/bold] {data.release_date}")
    if data.runtime:
        lines.append(f"[bold]Runtime:[/bold] {data.runtime} min")
    if data.rating:
        lines.append(f"[bold]Rating:[/bold] {data.rating.rating}/10 ({data.rating.votes} votes)")
    if data.genres:
        lines.append(f"[bold]Genres:[/bold] {', '.join(data.genres)}")
    if data.actresses:
        actress_names = [a.full_name for a in data.actresses]
        lines.append(f"[bold]Actresses:[/bold] {', '.join(actress_names)}")
    if data.description:
        desc = data.description[:200] + "..." if len(data.description) > 200 else data.description
        lines.append(f"\n[dim]{desc}[/dim]")

    content = "\n".join(lines)
    console.print(Panel(content, title=f"🎬 {data.id}", border_style="cyan"))


if __name__ == "__main__":
    app()
