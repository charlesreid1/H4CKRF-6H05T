"""Grant subcommands — ``grant tx / list / revoke``.

Pure CLI; actual work is one ``PermissionService.*`` call each.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from hackrf_agent.cli.parsing import parse_band, parse_duration, parse_gain_db
from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.permission_service import PermissionService

grant_app = typer.Typer(no_args_is_help=True, help="Manage TX grants.")

_console = Console()


@grant_app.command("tx")
def grant_tx(
    band: str = typer.Argument(..., help="Band spec, e.g. '433.05-434.79M' or '315M'."),
    for_: str = typer.Option(..., "--for", help="Grant duration, e.g. '30m', '2h', '90s'."),
    max_gain: int = typer.Option(
        20,
        "--max-gain",
        help="Maximum TX VGA gain (dB, 0-47).",
    ),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> None:
    """Issue a scoped, time-limited TX grant."""
    start_hz, stop_hz = parse_band(band)
    ttl = parse_duration(for_)
    gain = parse_gain_db(max_gain)
    settings = _settings_from_ctx(ctx)
    asyncio.run(_grant_tx(settings, start_hz, stop_hz, gain, ttl))


async def _grant_tx(
    settings: SettingsService,
    start_hz: int,
    stop_hz: int,
    max_gain_db: int,
    ttl_seconds: int,
) -> None:
    settings.home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(settings.db_path)
    perms = PermissionService(settings.db_path)
    grant = await perms.grant(
        kind="tx",
        band_start_hz=start_hz,
        band_stop_hz=stop_hz,
        max_gain_db=max_gain_db,
        ttl_seconds=ttl_seconds,
    )
    _console.print(
        f"[green]Granted[/] TX {start_hz}–{stop_hz} Hz "
        f"(max_gain={max_gain_db} dB) until "
        f"[bold]{grant.expires_at.astimezone().isoformat(timespec='seconds')}[/]"
    )
    _console.print(f"[dim]id: {grant.id}[/]")


@grant_app.command("list")
def grant_list(ctx: typer.Context = typer.Context) -> None:  # type: ignore[assignment]
    """List active TX grants."""
    settings = _settings_from_ctx(ctx)
    asyncio.run(_grant_list(settings))


async def _grant_list(settings: SettingsService) -> None:
    settings.home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(settings.db_path)
    perms = PermissionService(settings.db_path)
    grants = await perms.list_active()
    if not grants:
        _console.print("[dim]No active grants.[/]")
        return
    table = Table(title="Active TX grants")
    table.add_column("id", style="dim")
    table.add_column("band (Hz)")
    table.add_column("max_gain_db", justify="right")
    table.add_column("expires (local)")
    for g in grants:
        table.add_row(
            str(g.id),
            f"{g.band_start_hz}–{g.band_stop_hz}",
            str(g.max_gain_db),
            g.expires_at.astimezone().isoformat(timespec="seconds"),
        )
    _console.print(table)


@grant_app.command("revoke")
def grant_revoke(
    grant_id: str = typer.Argument(..., help="Grant UUID from `grant list`."),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> None:
    """Revoke a specific grant by id."""
    try:
        uid = UUID(grant_id)
    except ValueError as exc:
        _console.print(f"[red]Not a valid UUID: {grant_id}[/]")
        raise typer.Exit(code=2) from exc
    settings = _settings_from_ctx(ctx)
    asyncio.run(_grant_revoke(settings, uid))


async def _grant_revoke(settings: SettingsService, grant_id: UUID) -> None:
    settings.home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(settings.db_path)
    perms = PermissionService(settings.db_path)
    ok = await perms.revoke(grant_id)
    if ok:
        _console.print(f"[yellow]Revoked[/] {grant_id}")
    else:
        _console.print(f"[dim]Grant {grant_id} not found or already revoked.[/]")


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    """Read the SettingsService the top-level main.py stored in ctx.obj."""
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
