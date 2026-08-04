"""Typed exceptions for the HackRF hardware layer.

Every hardware-facing error inherits from :class:`HackrfError`. Callers
``except HackrfError:`` at the executor boundary and translate to
``CommandResult(success=False, error=...)``.

There are exactly five exceptions in this module. Do not add a sixth
without discussion. Do not use these outside ``hackrf_agent.hw.*``.
"""

from __future__ import annotations


class HackrfError(Exception):
    """Base for all hardware-facing errors from hackrf_agent.hw.*"""


class HackrfNotFoundError(HackrfError):
    """No HackRF device enumerated on the USB bus."""


class HackrfBusyError(HackrfError):
    """A HackRF device is present but already claimed by another handle."""


class KillSwitchTriggered(HackrfError):  # noqa: N818
    """The shared stop_event was set mid-operation; caller aborted cleanly."""


class InvalidHackrfArgError(HackrfError, ValueError):
    """Caller supplied an argument outside the valid grid (rate, gain, freq).

    Inherits from ``ValueError`` so ``except ValueError:`` in older callers
    still catches it, but is preferred at the driver boundary.
    """


class HackrfTimeoutError(HackrfError):
    """A libhackrf operation did not complete within the caller's timeout."""
