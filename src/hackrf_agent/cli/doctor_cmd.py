"""``doctor`` — first-run diagnostic with an optional --strict pre-flight."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema

_console = Console()


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    # Hard failures cause a non-zero exit even without --strict; soft
    # warnings only fail the exit code under --strict.
    hard: bool = True


def doctor(
    strict: bool = typer.Option(
        False,
        "--strict",
        help=(
            "Also validate: pyhackrf importable, hackrf_info firmware, "
            "corpus discoverable + records/*.json valid, audit DB row "
            "count under 1M. Use before an event: 'green board, safe to fly.'"
        ),
    ),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> None:
    """Run first-run diagnostics; print a checklist."""
    settings = _settings_from_ctx(ctx)
    checks = asyncio.run(_run_checks(settings, strict=strict))
    _render(checks)
    hard_failures = [c for c in checks if not c.ok and c.hard]
    soft_failures = [c for c in checks if not c.ok and not c.hard]
    if hard_failures or (strict and soft_failures):
        raise typer.Exit(code=1)


async def _run_checks(settings: SettingsService, *, strict: bool) -> list[Check]:
    checks: list[Check] = []

    # 1. Home dir writable. HARD.
    try:
        settings.home_dir.mkdir(parents=True, exist_ok=True)
        checks.append(Check("home_dir", True, str(settings.home_dir), hard=True))
    except OSError as e:
        checks.append(Check("home_dir", False, f"cannot create: {e}", hard=True))

    # 2. DB migrations up to date. HARD.
    try:
        await ensure_schema(settings.db_path)
        checks.append(Check("db_schema", True, str(settings.db_path), hard=True))
    except Exception as e:
        checks.append(Check("db_schema", False, str(e), hard=True))

    # 3. API key present. SOFT — the MCP server itself doesn't need it,
    # only the chat CLI does. A fresh clone without the key can still
    # run `hackrf-agent mcp`.
    if settings.get_api_key():
        checks.append(Check("api_key", True, "OPENROUTER_API_KEY set", hard=False))
    else:
        checks.append(
            Check(
                "api_key",
                False,
                "OPENROUTER_API_KEY not set — required for `hackrf-agent chat` "
                "but not for `hackrf-agent mcp`",
                hard=False,
            )
        )

    # 4. HackRF enumerates. HARD.
    checks.append(await _check_hackrf())

    if strict:
        checks.append(_check_pyhackrf_importable())
        checks.append(_check_hackrf_firmware())
        checks.append(_check_corpus_discoverable())
        checks.append(_check_records_valid())
        checks.append(await _check_audit_db_size(settings))

    return checks


async def _check_hackrf() -> Check:
    from hackrf_agent.hw.exceptions import HackrfError, InvalidHackrfArgError
    from hackrf_agent.hw.hackrf_subprocess import run_hackrf_tool

    try:
        result = await run_hackrf_tool(["hackrf_info"], timeout_s=5)
    except InvalidHackrfArgError as e:
        return Check("hackrf", False, f"hackrf_info missing on PATH: {e}", hard=True)
    except HackrfError as e:
        return Check("hackrf", False, f"hackrf_info failed: {e}", hard=True)
    first_line = result.stdout.splitlines()[0] if result.stdout else "(no output)"
    return Check("hackrf", True, first_line, hard=True)


def _check_pyhackrf_importable() -> Check:
    """python-hackrf importable — normally only checked lazily on connect."""
    try:
        import hackrf as _hackrf  # noqa: F401
    except Exception as e:
        return Check(
            "pyhackrf",
            False,
            f"import failed: {e}. Install: pip install pyhackrf",
            hard=True,
        )
    return Check("pyhackrf", True, "importable", hard=True)


def _check_hackrf_firmware() -> Check:
    """Warn if hackrf_info firmware string looks obviously old. Soft — the
    firmware may work fine; we just warn.
    """
    try:
        r = subprocess.run(
            ["hackrf_info"], capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return Check("firmware", False, f"hackrf_info: {e}", hard=False)
    if r.returncode != 0:
        return Check(
            "firmware", False, f"hackrf_info exit {r.returncode}", hard=False
        )
    firmware_line = ""
    for line in r.stdout.splitlines():
        if "Firmware Version" in line:
            firmware_line = line.strip()
            break
    if not firmware_line:
        return Check("firmware", True, "(no Firmware Version line)", hard=False)
    return Check("firmware", True, firmware_line, hard=False)


def _check_corpus_discoverable() -> Check:
    from hackrf_agent.domain.knowledge import default_paths

    try:
        paths = default_paths()
    except Exception as e:
        return Check("corpus", False, f"discover failed: {e}", hard=True)
    manifest = paths.root / "MANIFEST.md"
    if not manifest.is_file():
        return Check(
            "corpus", False, f"MANIFEST.md missing under {paths.root}", hard=True
        )
    return Check("corpus", True, str(paths.root), hard=True)


def _check_records_valid() -> Check:
    """Shell out to scripts/validate_knowledge_records.py. HARD."""
    from hackrf_agent.domain.knowledge import default_paths

    try:
        paths = default_paths()
    except Exception as e:
        return Check("records", False, f"corpus root missing: {e}", hard=True)
    script = paths.root.parent / "scripts" / "validate_knowledge_records.py"
    if not script.is_file():
        return Check(
            "records", False, f"validator missing at {script}", hard=True
        )
    try:
        r = subprocess.run(
            ["python", str(script)], capture_output=True, text=True, timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return Check("records", False, f"validator error: {e}", hard=True)
    if r.returncode != 0:
        return Check(
            "records", False, (r.stderr or r.stdout).strip()[:200], hard=True
        )
    return Check("records", True, "records/*.json validated", hard=True)


async def _check_audit_db_size(settings: SettingsService) -> Check:
    """Warn at 100k rows, fail at 1M. Adds a nudge to rotate."""
    from hackrf_agent.domain.audit_service import AuditService

    if not Path(settings.db_path).exists():
        return Check("audit_size", True, "(empty)", hard=False)
    async with AuditService(settings.db_path) as audit:
        stats = await audit.stats()
    detail = f"{stats.row_count:,} rows ({stats.size_bytes:,} bytes)"
    if stats.row_count >= 1_000_000:
        return Check(
            "audit_size",
            False,
            detail + " — run `hackrf-agent audit rotate`",
            hard=True,
        )
    if stats.row_count >= 100_000:
        return Check(
            "audit_size",
            False,
            detail + " — consider `hackrf-agent audit rotate`",
            hard=False,
        )
    return Check("audit_size", True, detail, hard=False)


def _render(checks: list[Check]) -> None:
    table = Table(title="hackrf-agent doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")
    for c in checks:
        if c.ok:
            status = "[green]OK[/]"
        elif c.hard:
            status = "[red]FAIL[/]"
        else:
            status = "[yellow]WARN[/]"
        table.add_row(c.name, status, c.detail)
    _console.print(table)


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
