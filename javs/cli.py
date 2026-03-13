"""CLI interface for javs using Typer.

Replaces Javinizer's complex single-function CmdletBinding with clean subcommands.
"""

from __future__ import annotations

import asyncio
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
    engine = JavsEngine(cfg)

    with console.status("[bold green]Sorting files...", spinner="dots"):
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
    engine = JavsEngine(cfg)

    scraper_list = scrapers.split(",") if scrapers else None

    with console.status("[bold cyan]Searching...", spinner="dots"):
        data = asyncio.run(engine.find(movie_id, scraper_names=scraper_list))

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
    action: str = typer.Argument("show", help="Action: show, edit, create, path."),
    config_path: Path | None = typer.Option(None, "--config", "-c", help="Path to config file."),
) -> None:
    """⚙️ Manage configuration."""
    from javs.config import create_default_config, load_config
    from javs.config.loader import get_default_config_path

    path = config_path or get_default_config_path()

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
        success = sync_user_config()
        if success:
            console.print(
                f"[green]Successfully synced and upgraded local config file at {path}[/green]"
            )
        else:
            console.print("[red]Failed to sync configuration. Check logs for details.[/red]")
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
