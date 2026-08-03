"""Approval as a ``Protocol``. Two test doubles; production impl in Part 7."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from hackrf_agent.domain.models import ExecuteCommand, RiskAssessment


@runtime_checkable
class ApprovalPort(Protocol):
    """Ask the human to approve a MEDIUM- or HIGH-risk command.

    Implementations MUST:
    - Return ``True`` iff the user affirmatively approved this specific
      command.
    - Never mutate ``command`` or ``risk``.
    - Never touch hardware or persistence.
    - Be safe to call from an ``async`` context; block on the user, not on
      the event loop, if possible.

    The executor only calls ``request`` when ``risk.requires_confirmation``
    is True. LOW commands skip approval; BLOCKED commands are refused
    before this port is reached.
    """

    async def request(
        self, command: ExecuteCommand, risk: RiskAssessment
    ) -> bool: ...


@dataclass
class FakeApprovalPort:
    """Test double: returns a canned answer and records every call.

    Set ``answer=True`` to approve, ``False`` to deny. If ``answers`` is
    non-empty, entries are popped from the head — useful for tests that
    exercise a sequence of approvals.

    ``.calls`` is a list of ``(command, risk)`` tuples, populated in call
    order. Tests assert on this to verify the executor called (or did not
    call) approval when expected.
    """

    answer: bool = True
    answers: list[bool] = field(default_factory=list)
    calls: list[tuple[ExecuteCommand, RiskAssessment]] = field(default_factory=list)

    async def request(
        self, command: ExecuteCommand, risk: RiskAssessment
    ) -> bool:
        self.calls.append((command, risk))
        if self.answers:
            return self.answers.pop(0)
        return self.answer


class AlwaysAllowApprovalPort:
    """Convenience impl for scripts that pre-authorize everything.

    Do NOT use this in production. The docstring must say so; leave the
    warning in place even if a reviewer suggests removing it.
    """

    async def request(
        self, command: ExecuteCommand, risk: RiskAssessment
    ) -> bool:
        return True
