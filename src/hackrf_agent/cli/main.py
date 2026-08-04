"""The Typer app.  One file that mounts every subcommand."""

from __future__ import annotations

from pathlib import Path

import typer

from hackrf_agent.cli.audit_cmd import audit_app
from hackrf_agent.cli.chat_cmd import chat
from hackrf_agent.cli.doctor_cmd import doctor
from hackrf_agent.cli.permissions_cmd import grant_app
from hackrf_agent.cli.settings import DEFAULT_HOME, SettingsService

app = typer.Typer(
    name="hackrf-agent",
    help="AI control plane for HackRF One — safe, auditable SDR via LLM tool-use.",
    no_args_is_help=True,
)

app.add_typer(grant_app, name="grant")
app.add_typer(audit_app, name="audit")
app.command("chat")(chat)
app.command("doctor")(doctor)


@app.callback()
def _root(
    ctx: typer.Context,
    home_dir: Path = typer.Option(  # noqa: B008
        DEFAULT_HOME,
        "--home-dir",
        help="Override the default ~/.hackrf-agent directory.",
    ),
) -> None:
    """Configure shared state visible to every subcommand via ctx.obj."""
    ctx.obj = SettingsService(home_dir=home_dir)
