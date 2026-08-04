"""``doctor`` — first-run diagnostic + ``set-api-key`` helper."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema

_console = Console()


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def doctor(ctx: typer.Context = typer.Context) -> None:  # type: ignore[assignment]
    """Run first-run diagnostics; print a checklist."""
    settings = _settings_from_ctx(ctx)
    checks = asyncio.run(_run_checks(settings))
    _render(checks)
    if not all(c.ok for c in checks):
        raise typer.Exit(code=1)


async def _run_checks(settings: SettingsService) -> list[Check]:
    checks: list[Check] = []

    # 1. Home dir writable.
    try:
        settings.home_dir.mkdir(parents=True, exist_ok=True)
        checks.append(Check("home_dir", True, str(settings.home_dir)))
    except OSError as e:
        checks.append(Check("home_dir", False, f"cannot create: {e}"))

    # 2. DB migrations up to date.
    try:
        await ensure_schema(settings.db_path)
        checks.append(Check("db_schema", True, str(settings.db_path)))
    except Exception as e:  # noqa: BLE001
        checks.append(Check("db_schema", False, str(e)))

    # 3. API key present.
    if settings.get_api_key():
        checks.append(Check("api_key", True, "present in keychain"))
    else:
        checks.append(
            Check(
                "api_key",
                False,
                "not set — run `hackrf-agent set-api-key`",
            )
        )

    # 4. HackRF enumerates.
    checks.append(await _check_hackrf())

    return checks


async def _check_hackrf() -> Check:
    from hackrf_agent.hw.exceptions import HackrfError, InvalidHackrfArgError
    from hackrf_agent.hw.hackrf_subprocess import run_hackrf_tool

    try:
        result = await run_hackrf_tool(["hackrf_info"], timeout_s=5)
    except InvalidHackrfArgError as e:
        return Check("hackrf", False, f"hackrf_info missing on PATH: {e}")
    except HackrfError as e:
        return Check("hackrf", False, f"hackrf_info failed: {e}")
    first_line = (
        result.stdout.splitlines()[0] if result.stdout else "(no output)"
    )
    return Check("hackrf", True, first_line)


def _render(checks: list[Check]) -> None:
    table = Table(title="hackrf-agent doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for c in checks:
        status = "[green]OK[/]" if c.ok else "[red]FAIL[/]"
        table.add_row(c.name, status, c.detail)
    _console.print(table)


def set_api_key(
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
    key: str
    | None = typer.Option(
        None,
        "--key",
        help="API key value; if omitted, prompted interactively.",
    ),
) -> None:
    """Store an Anthropic API key in the OS keychain."""
    settings = _settings_from_ctx(ctx)
    if key is None:
        key = Prompt.ask("Paste Anthropic API key", password=True)
    if not key.strip():
        _console.print("[red]No key provided; aborting.[/]")
        raise typer.Exit(code=2)
    settings.set_api_key(key)
    _console.print("[green]API key stored in keychain.[/]")


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
