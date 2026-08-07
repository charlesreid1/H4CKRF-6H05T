"""Session-level cumulative-TX-time budget.

Belt-and-suspenders companion to ``CaptureBudget``. The RiskAssessor
gates each individual TX by band+gain; grants bound the frequency range
and gain ceiling; this bounds the *cumulative* on-air time for the
session, so a flood of short in-grant TX calls cannot silently sum to a
long transmission.

The budget is read from the ``MAX_TX_SECONDS`` env var at
executor-construction time. When unset or empty, the budget is disabled
(no cap). When set to a positive number, the cumulative TX duration
across every ``transmit_iq`` call in the session must stay under the
cap; a call that would push the total over is refused before the driver
is invoked, with a matching BLOCKED audit row.

State is per-executor-instance (i.e. per session). Restarting the
process resets the counter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class TxBudget:
    """Mutable per-session accumulator for cumulative TX duration."""

    max_seconds: float | None = None
    accumulated_seconds: float = 0.0

    @classmethod
    def from_env(cls, env_var: str = "MAX_TX_SECONDS") -> "TxBudget":
        """Construct from an env var. Empty / unset / non-numeric → disabled."""
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            return cls(max_seconds=None)
        try:
            seconds = float(raw)
        except ValueError:
            return cls(max_seconds=None)
        if seconds <= 0:
            return cls(max_seconds=None)
        return cls(max_seconds=seconds)

    def remaining_seconds(self) -> float:
        """Remaining budget in seconds. Returns +inf when disabled."""
        if self.max_seconds is None:
            return float("inf")
        return max(0.0, self.max_seconds - self.accumulated_seconds)

    def would_exceed(self, requested_seconds: float) -> bool:
        """True iff *requested_seconds* would push cumulative over the cap."""
        if self.max_seconds is None:
            return False
        return self.accumulated_seconds + requested_seconds > self.max_seconds

    def charge(self, seconds: float) -> None:
        """Record a completed TX against the budget."""
        if seconds < 0:
            return
        self.accumulated_seconds += seconds
