"""The stop-event owner.  Wires SIGINT → stop_event + TX revoke.

Distinguishes single-Ctrl-C-graceful from double-Ctrl-C-hard-exit.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time
from dataclasses import dataclass, field

from hackrf_agent.domain.permission_service import PermissionService

logger = logging.getLogger(__name__)

DOUBLE_TAP_WINDOW_S: float = 2.0


@dataclass
class KillSwitch:
    """Coordinates the shared stop event with SIGINT and grant revocation.

    Construct one per chat session. Call ``install_handler(loop)`` while
    inside a running event loop. Call ``uninstall_handler(loop)`` on
    session end.

    Behavior:
      - First SIGINT: set stop_event, revoke all TX grants, log INFO.
        Callers observing stop_event raise KillSwitchTriggered on their
        next check.
      - Second SIGINT within DOUBLE_TAP_WINDOW_S: raise
        KeyboardInterrupt into the loop (via loop.stop()) so the process
        exits.
      - Two SIGINTs more than DOUBLE_TAP_WINDOW_S apart: each acts as a
        first-SIGINT.
    """

    stop_event: asyncio.Event
    permissions: PermissionService
    _last_press_s: float = field(default=0.0, init=False)
    _installed: bool = field(default=False, init=False)

    def install_handler(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._installed:
            return
        loop.add_signal_handler(signal.SIGINT, lambda: self._on_sigint(loop))
        self._installed = True

    def uninstall_handler(self, loop: asyncio.AbstractEventLoop) -> None:
        if not self._installed:
            return
        with contextlib.suppress(NotImplementedError):
            # Windows can't add signal handlers to an asyncio loop —
            # not a supported platform for this project.
            loop.remove_signal_handler(signal.SIGINT)
        self._installed = False

    # ------------------------------------------------------------------

    def _on_sigint(self, loop: asyncio.AbstractEventLoop) -> None:
        now = time.monotonic()
        if now - self._last_press_s < DOUBLE_TAP_WINDOW_S:
            logger.warning("kill switch: double-Ctrl-C; hard-exiting")
            loop.stop()
            return
        self._last_press_s = now
        # First (or expired-window) press.
        if not self.stop_event.is_set():
            self.stop_event.set()
        logger.info("kill switch: SIGINT received; stop_event set, revoking TX")
        # Fire-and-forget the revoke — we can't await inside a signal handler.
        loop.create_task(self._revoke_and_log())

    async def _revoke_and_log(self) -> None:
        try:
            n = await self.permissions.revoke_all_tx()
            logger.info("kill switch: revoked %d TX grants", n)
        except Exception as e:  # noqa: BLE001
            logger.exception("kill switch: TX revoke failed: %s", e)
