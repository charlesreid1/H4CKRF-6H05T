"""Session-level cumulative-capture-time budget.

Belt-and-suspenders to the per-command duration limits enforced by
``RiskAssessor._assess_capture_iq``. Where the per-command limit stops
"one 30-minute capture," the session budget stops "sixty 30-second
captures summing to 30 minutes."

The budget is read from the ``MAX_CAPTURE_MINUTES`` env var at
executor-construction time. When unset or empty, the budget is
disabled (no cap). When set to a positive number, the cumulative
duration across every ``capture_iq`` call in the session must stay
under the cap; a call that would push the total over is refused with
a BLOCKED-style result before any RF activity.

State is per-executor-instance (i.e. per session). Restarting the
process resets the counter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class CaptureBudget:
    """Mutable per-session accumulator for cumulative capture duration."""

    max_seconds: float | None = None
    accumulated_seconds: float = 0.0

    @classmethod
    def from_env(cls, env_var: str = "MAX_CAPTURE_MINUTES") -> CaptureBudget:
        """Construct from an env var. Empty / unset / non-numeric → disabled."""
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            return cls(max_seconds=None)
        try:
            minutes = float(raw)
        except ValueError:
            return cls(max_seconds=None)
        if minutes <= 0:
            return cls(max_seconds=None)
        return cls(max_seconds=minutes * 60.0)

    def remaining_seconds(self) -> float:
        """Return the remaining budget in seconds (positive = time left).

        Returns ``float('inf')`` when the budget is disabled.
        """
        if self.max_seconds is None:
            return float("inf")
        return max(0.0, self.max_seconds - self.accumulated_seconds)

    def would_exceed(self, requested_seconds: float) -> bool:
        """True iff *requested_seconds* would push cumulative over the cap."""
        if self.max_seconds is None:
            return False
        return self.accumulated_seconds + requested_seconds > self.max_seconds

    def charge(self, seconds: float) -> None:
        """Record a completed (or in-progress) capture against the budget."""
        if seconds < 0:
            return
        self.accumulated_seconds += seconds
