"""The concrete ``ApprovalPort`` — terminal-based approval prompts.

MEDIUM commands: single Y/n via ``rich.prompt.Confirm``.
HIGH commands: user must type the literal string ``CONFIRM``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from rich.console import Console
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from hackrf_agent.domain.approval import ApprovalPort  # noqa: F401 — Protocol
from hackrf_agent.domain.models import ExecuteCommand, RiskAssessment, RiskLevel


@dataclass
class CliApprovalPort:
    """Terminal-based approval prompt.

    MEDIUM commands: single Y/n via ``Confirm.ask``.
    HIGH commands: user must type the literal string ``CONFIRM`` (typo-safe
      double-tap equivalent).

    ``auto_approve_medium=True`` skips the MEDIUM prompt and returns True.
    HIGH is NEVER auto-approved regardless of the flag.
    """

    console: Console
    auto_approve_medium: bool = False

    async def request(
        self, command: ExecuteCommand, risk: RiskAssessment,
    ) -> bool:
        loop = asyncio.get_running_loop()

        # Render the pending command block; rich handles ANSI itself.
        self._render_pending(command, risk)

        if risk.level == RiskLevel.MEDIUM and self.auto_approve_medium:
            self.console.print("[dim]auto-approved (auto_approve_medium=True)[/]")
            return True

        # rich prompts are blocking. Push them to a thread so the loop stays
        # responsive to SIGINT + audit writer.
        if risk.level == RiskLevel.MEDIUM:
            return await loop.run_in_executor(
                None, lambda: Confirm.ask("[bold]Approve?[/]", default=False),
            )
        if risk.level == RiskLevel.HIGH:
            typed = await loop.run_in_executor(
                None,
                lambda: Prompt.ask(
                    "[bold red]Type CONFIRM to approve (anything else denies)[/]",
                    default="",
                ),
            )
            return typed.strip() == "CONFIRM"
        # LOW/BLOCKED should never reach here — the executor filters them out.
        return False

    # ------------------------------------------------------------------

    def _render_pending(
        self, command: ExecuteCommand, risk: RiskAssessment,
    ) -> None:
        color = {
            RiskLevel.LOW: "green",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.HIGH: "red",
            RiskLevel.BLOCKED: "red",
        }[risk.level]
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        table.add_row("Action:", command.action.value)
        table.add_row("Risk:", f"[{color}]{risk.level.value}[/{color}]")
        table.add_row("Reason:", risk.reason)
        table.add_row("Justification:", command.justification)
        table.add_row("Expected effect:", command.expected_effect)
        for k, v in command.args.items():
            table.add_row(f"  args.{k}:", rich_escape(str(v)))
        self.console.print(Panel(table, title="Pending command", border_style=color))
