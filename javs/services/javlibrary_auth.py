"""Helpers for Javlibrary Cloudflare credential prompts and validation."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from javs.config import JavsConfig, save_config
from javs.services.http import CloudflareBlockedError, HttpClient

console = Console()


@dataclass(slots=True)
class JavlibraryCredentials:
    """Runtime credentials required for Javlibrary Cloudflare access."""

    cf_clearance: str
    browser_user_agent: str


def is_interactive_terminal() -> bool:
    """Return True when the process can reasonably prompt for terminal input."""
    return sys.stdin.isatty()


def notify_javlibrary_cookie_required() -> None:
    """Best-effort desktop notification for interactive Cloudflare recovery."""
    title = "Javlibrary credentials required"
    message = "Return to the terminal to enter cf_clearance and the browser User-Agent."

    try:
        if sys.platform == "darwin":
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{title}"',
                ],
                check=False,
                capture_output=True,
                timeout=5,
            )
            return

        if sys.platform.startswith("linux"):
            if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                return
            if shutil.which("notify-send") is None:
                return
            subprocess.run(
                ["notify-send", title, message],
                check=False,
                capture_output=True,
                timeout=5,
            )
            return

        if sys.platform.startswith("win"):
            if shutil.which("powershell") is None:
                return
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[System.Windows.Forms.MessageBox]::Show("
                f"'{message}','{title}') | Out-Null"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                check=False,
                capture_output=True,
                timeout=5,
            )
    except Exception:
        # Notifications are best-effort only.
        return


def print_cloudflare_guidance(exc: CloudflareBlockedError) -> None:
    """Render Cloudflare recovery instructions in a readable terminal block."""
    body = exc.guidance.strip() if exc.guidance else str(exc)
    console.print(Panel(body, title="Javlibrary Cloudflare", border_style="yellow"))


def prompt_for_javlibrary_credentials(
    existing: JavlibraryCredentials | None = None,
) -> JavlibraryCredentials | None:
    """Prompt the user for Javlibrary Cloudflare credentials."""
    current_ua = existing.browser_user_agent if existing else ""

    cf_clearance = typer.prompt(
        "Javlibrary cf_clearance",
        hide_input=True,
        confirmation_prompt=False,
    ).strip()
    if not cf_clearance:
        return None

    if current_ua:
        browser_user_agent = current_ua.strip()
        console.print("[cyan]Reusing the browser User-Agent already saved in config.[/cyan]")
    else:
        browser_user_agent = typer.prompt(
            "Javlibrary browser User-Agent",
        ).strip()

    if not browser_user_agent:
        return None

    return JavlibraryCredentials(
        cf_clearance=cf_clearance,
        browser_user_agent=browser_user_agent,
    )


async def validate_javlibrary_credentials(
    config: JavsConfig,
    credentials: JavlibraryCredentials,
) -> None:
    """Validate Javlibrary credentials with a best-effort live request."""
    proxy_url = config.proxy.url if config.proxy.enabled else None
    timeout_seconds = (
        config.proxy.timeout_seconds
        if config.proxy.enabled
        else config.sort.download.timeout_seconds
    )
    client = HttpClient(
        proxy_url=proxy_url,
        timeout_seconds=timeout_seconds,
        max_concurrent=1,
        max_retries=config.proxy.max_retries if config.proxy.enabled else 1,
        cf_clearance=credentials.cf_clearance,
        cf_user_agent=credentials.browser_user_agent,
        verify_ssl=False,
    )
    test_url = f"{config.javlibrary.base_url.rstrip('/')}/en/"
    use_proxy = bool(config.proxy.enabled and config.scrapers.use_proxy.get("javlibrary", False))

    async with client:
        body = await client.get_cf(test_url, use_proxy=use_proxy)

    if not body.strip():
        raise CloudflareBlockedError("Javlibrary returned an empty response body")


def apply_javlibrary_credentials(
    config: JavsConfig,
    credentials: JavlibraryCredentials,
) -> None:
    """Apply Javlibrary credentials to an in-memory config object."""
    config.javlibrary.cookie_cf_clearance = credentials.cf_clearance
    config.javlibrary.browser_user_agent = credentials.browser_user_agent


async def configure_javlibrary_credentials(
    config: JavsConfig,
    config_path: Path,
    *,
    prompt_on_missing: bool = True,
    send_notification: bool = False,
    save_on_success: bool = True,
) -> JavlibraryCredentials | None:
    """Prompt, validate, and optionally save Javlibrary credentials."""
    if send_notification:
        notify_javlibrary_cookie_required()

    existing = JavlibraryCredentials(
        cf_clearance=config.javlibrary.cookie_cf_clearance,
        browser_user_agent=config.javlibrary.browser_user_agent,
    )

    if prompt_on_missing and not typer.confirm(
        "Javlibrary needs a fresh cf_clearance value. Enter it now?",
        default=True,
    ):
        return None

    credentials = prompt_for_javlibrary_credentials(existing=existing)
    if credentials is None:
        console.print("[red]Missing cf_clearance or User-Agent. Config was not saved.[/red]")
        return None

    apply_javlibrary_credentials(config, credentials)
    if save_on_success:
        await asyncio.to_thread(save_config, config, config_path)

    try:
        await validate_javlibrary_credentials(config, credentials)
    except Exception as exc:
        console.print(f"[red]Javlibrary credential test failed.[/red] Reason: {exc}")
        if isinstance(exc, CloudflareBlockedError) and exc.guidance:
            print_cloudflare_guidance(exc)
        return None

    console.print("[green]Saved Javlibrary cf_clearance and browser User-Agent.[/green]")
    return credentials
