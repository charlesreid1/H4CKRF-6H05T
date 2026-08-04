"""``audit tail`` subcommand — pretty-print recent audit rows."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from hackrf_agent.cli.settings import SettingsService
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService

audit_app = typer.Typer(no_args_is_help=True, help="Query the audit log.")

_console = Console()


@audit_app.command("tail")
def audit_tail(
    session: str | None = typer.Option(
        None, "--session", help="Filter by session id."
    ),
    trace: str | None = typer.Option(
        None, "--trace", help="Filter by trace id (UUID)."
    ),
    limit: int = typer.Option(50, "--limit", help="Max rows to display."),
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
) -> None:
    """Print recent audit rows in table form."""
    trace_uuid: UUID | None = None
    if trace is not None:
        try:
            trace_uuid = UUID(trace)
        except ValueError as exc:
            _console.print(f"[red]Not a valid trace UUID: {trace}[/]")
            raise typer.Exit(code=2) from exc
    settings = _settings_from_ctx(ctx)
    asyncio.run(_audit_tail(settings, session, trace_uuid, limit))


async def _audit_tail(
    settings: SettingsService,
    session_id: str | None,
    trace_id: UUID | None,
    limit: int,
) -> None:
    settings.home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(settings.db_path)
    async with AuditService(settings.db_path) as audit:
        rows = await audit.query(
            session_id=session_id, trace_id=trace_id, limit=limit,
        )
    if not rows:
        _console.print("[dim]No audit rows match.[/]")
        return
    table = Table(title=f"Audit — last {len(rows)} rows")
    table.add_column("time (local)", style="dim")
    table.add_column("event")
    table.add_column("action")
    table.add_column("risk")
    table.add_column("ms", justify="right")
    table.add_column("trace", style="dim")
    for r in rows:
        table.add_row(
            datetime.fromtimestamp(r.timestamp)
            .astimezone()
            .isoformat(timespec="seconds"),
            r.event.value,
            r.action.value if r.action else "",
            r.risk_level.value if r.risk_level else "",
            str(r.duration_ms) if r.duration_ms is not None else "",
            str(r.trace_id)[:8],
        )
    _console.print(table)


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
