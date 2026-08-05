"""McpApprovalPort — bridges ApprovalPort to MCP elicitation.

MEDIUM and HIGH commands need a human decision. Under MCP the server pushes
an ``elicitation/create`` request back to the host via ``session.elicit()``;
the host renders it to the human; the human responds; the server resumes the
command.

This module implements the ``ApprovalPort`` protocol so the executor doesn't
know the transport changed. It formats a plain-text summary and uses the
MCP session's elicitation mechanism.

The session is passed via a ``ContextVar`` set by ``server.py`` inside the
``on_call_tool`` handler.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

from mcp.server.session import ServerSession

from hackrf_agent.domain.models import ExecuteCommand, RiskAssessment, RiskLevel

logger = logging.getLogger(__name__)

# Set by the server's on_call_tool handler before invoking the executor.
_current_session: ContextVar[ServerSession | None] = ContextVar(
    "_current_mcp_session", default=None
)


class McpApprovalPort:
    """MCP elicitation-based approval.

    Pushes an ``elicitation/create`` (form mode) back to the host with a
    plain-text summary of the pending command. Both MEDIUM and HIGH use
    the same empty-properties schema so the host renders a plain
    Allow/Deny prompt — no form fields, no checkbox, no typed CONFIRM.
    The risk tier only changes the message text shown to the operator.

    Parameters:
        auto_approve_medium: If True, skip the elicitation for MEDIUM
            commands and return True. HIGH is NEVER auto-approved.
    """

    def __init__(
        self,
        *,
        auto_approve_medium: bool = False,
    ) -> None:
        self._auto_approve_medium = auto_approve_medium

    # ------------------------------------------------------------------
    # ApprovalPort protocol
    # ------------------------------------------------------------------

    async def request(
        self,
        command: ExecuteCommand,
        risk: RiskAssessment,
    ) -> bool:
        """Ask the human via MCP elicitation.

        Returns True iff the human approved. Returns False on deny,
        timeout, or when elicitation is unavailable.
        """
        # AUTO-APPROVE for MEDIUM (when flag is set).
        if risk.level == RiskLevel.MEDIUM and self._auto_approve_medium:
            logger.info("auto-approved MEDIUM command (auto_approve_medium=True)")
            return True

        session = _current_session.get()
        if session is None:
            logger.error(
                "No MCP session available — cannot request approval. "
                "Deny the command."
            )
            return False

        message = self._format_message(command, risk)
        requested_schema = self._elicitation_schema(risk)

        try:
            result = await session.elicit(
                message=message,
                requested_schema=requested_schema,
            )
        except Exception:
            logger.exception("elicit() call failed — treating as deny")
            return False

        if result is None:
            logger.info("elicit() returned None — treating as deny")
            return False

        # ElicitResult.action is "accept" | "decline" | "cancel".
        # The schema has no form fields — accept IS approval, at every tier.
        if result.action != "accept":
            logger.info("Operator did not accept elicitation (action=%s)", result.action)
            return False

        logger.info("Operator approved command")
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_message(
        command: ExecuteCommand,
        risk: RiskAssessment,
    ) -> str:
        """Format a plain-text summary matching CliApprovalPort's Rich panel."""
        lines = [
            f"Pending command: {command.action.value}",
            f"Risk level: {risk.level.value}",
            f"Reason: {risk.reason}",
            f"Justification: {command.justification}",
            f"Expected effect: {command.expected_effect}",
        ]
        for k, v in command.args.items():
            lines.append(f"  args.{k}: {v!s}")
        return "\n".join(lines)

    @staticmethod
    def _elicitation_schema(risk: RiskAssessment) -> dict[str, Any]:
        """Build the JSON Schema for the elicitation form.

        Empty properties at every tier so the host renders a bare
        Allow/Deny prompt with no form fields. The risk-tier signal reaches
        the operator through ``_format_message``, not the form shape.
        """
        del risk  # tier is reflected in the message text, not the schema
        return {
            "type": "object",
            "properties": {},
        }
