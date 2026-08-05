"""``doctor`` — first-run diagnostic."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema

_console = Console()


class Status(str, Enum):
    OK = "ok"
    WARN = "warn"      # optional feature unavailable; exit still 0
    FAIL = "fail"      # required feature broken; exit 1


@dataclass
class Check:
    name: str
    status: Status
    detail: str


def doctor(ctx: typer.Context = typer.Context) -> None:  # type: ignore[assignment]
    """Run first-run diagnostics; print a checklist."""
    settings = _settings_from_ctx(ctx)
    checks = asyncio.run(_run_checks(settings))
    _render(checks)
    if any(c.status is Status.FAIL for c in checks):
        raise typer.Exit(code=1)


async def _run_checks(settings: SettingsService) -> list[Check]:
    checks: list[Check] = []

    # 1. Home dir writable.
    try:
        settings.home_dir.mkdir(parents=True, exist_ok=True)
        checks.append(Check("home_dir", Status.OK, str(settings.home_dir)))
    except OSError as e:
        checks.append(Check("home_dir", Status.FAIL, f"cannot create: {e}"))

    # 2. DB migrations up to date.
    try:
        await ensure_schema(settings.db_path)
        checks.append(Check("db_schema", Status.OK, str(settings.db_path)))
    except Exception as e:  # noqa: BLE001
        checks.append(Check("db_schema", Status.FAIL, str(e)))

    # 3. API key present.
    if settings.get_api_key():
        checks.append(Check("api_key", Status.OK, "OPENROUTER_API_KEY set"))
    else:
        checks.append(
            Check(
                "api_key",
                Status.FAIL,
                "OPENROUTER_API_KEY not set — export it in your shell before running",
            )
        )

    # 4. HackRF enumerates.
    checks.append(await _check_hackrf())

    # 5. rtl_433 (optional — WARN on absent, never FAIL).
    checks.append(_check_rtl_433())

    # 6. urh_cli (optional — WARN on absent, never FAIL).
    checks.append(_check_urh())

    return checks


async def _check_hackrf() -> Check:
    from hackrf_agent.hw.exceptions import HackrfError, InvalidHackrfArgError
    from hackrf_agent.hw.hackrf_subprocess import run_hackrf_tool

    try:
        result = await run_hackrf_tool(["hackrf_info"], timeout_s=5)
    except InvalidHackrfArgError as e:
        return Check("hackrf", Status.FAIL, f"hackrf_info missing on PATH: {e}")
    except HackrfError as e:
        return Check("hackrf", Status.FAIL, f"hackrf_info failed: {e}")
    first_line = result.stdout.splitlines()[0] if result.stdout else "(no output)"
    return Check("hackrf", Status.OK, first_line)


def _check_rtl_433() -> Check:
    """Check for ``rtl_433`` on PATH.  Optional — WARN on absent, never FAIL."""
    import shutil

    exe = shutil.which("rtl_433")
    if exe is None:
        return Check(
            "rtl_433",
            Status.WARN,
            "rtl_433 not found — install: `brew install rtl_433` "
            "or see https://github.com/merbanan/rtl_433",
        )
    import subprocess

    try:
        result = subprocess.run(
            [exe, "-V"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError):
        return Check(
            "rtl_433",
            Status.WARN,
            f"rtl_433 found at {exe} but -V probe failed",
        )
    # rtl_433 -V prints version to stderr on some builds.
    version_line = (
        result.stdout.strip() or result.stderr.strip()
    ).splitlines()[0] if (result.stdout or result.stderr) else "unknown version"
    return Check("rtl_433", Status.OK, version_line)


def _check_urh() -> Check:
    """Check for ``urh_cli`` on PATH.  Optional — WARN on absent, never FAIL."""
    import shutil

    exe = shutil.which("urh_cli")
    if exe is None:
        return Check(
            "urh_cli",
            Status.WARN,
            "urh_cli not found — install: `pipx install urh` "
            "or see https://github.com/jopohl/urh",
        )
    import subprocess

    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError):
        return Check(
            "urh_cli",
            Status.WARN,
            f"urh_cli found at {exe} but --version probe failed",
        )
    version_line = (
        result.stdout.strip() or result.stderr.strip()
    ).splitlines()[0] if (result.stdout or result.stderr) else "unknown version"
    return Check("urh_cli", Status.OK, version_line)


def _render(checks: list[Check]) -> None:
    table = Table(title="hackrf-agent doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for c in checks:
        if c.status is Status.OK:
            status = "[green]OK[/]"
        elif c.status is Status.WARN:
            status = "[yellow]WARN[/]"
        else:
            status = "[red]FAIL[/]"
        table.add_row(c.name, status, c.detail)
    _console.print(table)


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
