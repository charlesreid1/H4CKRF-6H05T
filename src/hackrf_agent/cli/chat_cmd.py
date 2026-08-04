"""``chat`` — the interactive REPL.  Consumes ``HackrfAgent.chat(...)``
events and renders them with ``rich``.

This is the main event — the one command that wires together every
Part-2..6 building block under a single long-lived ``asyncio.run(...)``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.prompt import Prompt

from hackrf_agent.cli.approval import CliApprovalPort
from hackrf_agent.cli.kill_switch import KillSwitch
from hackrf_agent.cli.settings import Settings, SettingsService

if TYPE_CHECKING:
    from hackrf_agent.ai.agent import HackrfAgent
from hackrf_agent.data.db import ensure_schema
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.executor import CommandExecutor
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.result_formatter import ResultFormatter
from hackrf_agent.domain.risk_assessor import RiskAssessor
from hackrf_agent.domain.session import new_session

logger = logging.getLogger(__name__)
_console = Console()


def chat(
    ctx: typer.Context = typer.Context,  # type: ignore[assignment]
    auto_approve_medium: bool = typer.Option(
        False,
        "--auto-approve-medium",
        help="Skip the Y/n prompt for MEDIUM-risk commands.",
    ),
) -> None:
    """Start an interactive chat REPL with the HackRF agent."""
    settings = _settings_from_ctx(ctx)
    loaded = settings.load()
    api_key = settings.get_api_key()
    if not api_key:
        _console.print("[red]No API key found.[/] Run `hackrf-agent set-api-key`.")
        raise typer.Exit(code=1)
    asyncio.run(_run_chat(settings, loaded, api_key, auto_approve_medium))


async def _run_chat(
    settings: SettingsService,
    loaded: Settings,
    api_key: str,
    auto_approve_medium: bool,
) -> None:
    # Lazy imports so ``--help`` works without pyhackrf.
    from hackrf_agent.ai.agent import (
        HackrfAgent,
    )
    from hackrf_agent.ai.llm_client import AnthropicClient
    from hackrf_agent.hw.hackrf_driver import HackrfDriver

    settings.home_dir.mkdir(parents=True, exist_ok=True)
    await ensure_schema(settings.db_path)
    session_paths = new_session(settings.sessions_dir)
    session_id = session_paths.session_id
    _console.print(f"[dim]session {session_id} — Ctrl-C to stop; twice to exit[/]")

    stop_event = asyncio.Event()
    perms = PermissionService(settings.db_path)
    kill = KillSwitch(stop_event=stop_event, permissions=perms)
    loop = asyncio.get_running_loop()
    kill.install_handler(loop)

    try:
        async with (
            AuditService(settings.db_path) as audit,
            HackrfDriver(stop_event=stop_event) as driver,
        ):
            approval = CliApprovalPort(
                console=_console,
                auto_approve_medium=(auto_approve_medium or loaded.auto_approve_medium),
            )
            executor = CommandExecutor(
                session_id=session_id,
                risk_assessor=RiskAssessor(),
                permissions=perms,
                audit=audit,
                driver=driver,
                formatter=ResultFormatter(),
                approval=approval,
                session_paths=session_paths,
            )
            llm = AnthropicClient(model=loaded.model, api_key=api_key)
            agent = HackrfAgent(
                llm=llm,
                executor=executor,
                max_history_messages=loaded.max_history_messages,
            )
            await _repl(agent, stop_event)
    finally:
        kill.uninstall_handler(loop)


async def _repl(agent: HackrfAgent, stop_event: asyncio.Event) -> None:
    from hackrf_agent.ai.agent import (
        AgentError,
        AssistantText,
        ToolCallCompleted,
        ToolCallStarted,
        TurnEnded,
    )

    loop = asyncio.get_running_loop()
    while True:
        # Prompt for user input on a thread so SIGINT interrupts cleanly.
        try:
            user_text = await loop.run_in_executor(
                None,
                lambda: Prompt.ask("[bold cyan]you[/]", default=""),
            )
        except (EOFError, KeyboardInterrupt):
            _console.print("\n[dim]bye[/]")
            return
        if not user_text.strip():
            continue
        if user_text.strip().lower() in ("/quit", "/exit"):
            return
        stop_event.clear()  # fresh turn — clear any prior kill flag
        async for ev in agent.chat(user_text):
            if isinstance(ev, AssistantText):
                _console.print(f"[bold magenta]agent[/] {ev.text}")
            elif isinstance(ev, ToolCallStarted):
                _console.print(f"[dim]→ tool {ev.action} (justification: {ev.justification})[/]")
            elif isinstance(ev, ToolCallCompleted):
                if ev.result and ev.result.success:
                    _console.print(f"[green]← ok[/] {ev.result.message}")
                elif ev.result:
                    _console.print(f"[red]← fail[/] {ev.result.message}")
            elif isinstance(ev, TurnEnded):
                if ev.stop_reason == "refusal":
                    _console.print("[yellow](model refused)[/]")
            elif isinstance(ev, AgentError):
                _console.print(f"[red]! error[/] {ev.message}")


def _settings_from_ctx(ctx: typer.Context) -> SettingsService:
    settings = getattr(ctx, "obj", None)
    if not isinstance(settings, SettingsService):
        settings = SettingsService()
    return settings
