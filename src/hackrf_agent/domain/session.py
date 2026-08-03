"""Session-scoped on-disk layout. Pure paths + a factory. Zero business logic."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class SessionPaths:
    """On-disk layout for one running agent session.

    ``root``       — the session's top-level dir
    (e.g. ``~/.hackrf-agent/sessions/2026-08-03T14-30-11_ab12cd``).
    ``iq_dir``     — where ``capture_iq`` writes raw samples.
    ``summary_dir`` — where ``result_formatter`` writes JSON summaries.
    ``log_dir``    — for future stderr/stdout logs (unused in Part 5).

    Everything is under ``root``. Nothing outside ``root`` may be written
    by the executor. Tests pin this with a path-safety assertion.
    """

    session_id: str
    root: Path

    @property
    def iq_dir(self) -> Path:
        return self.root / "iq"

    @property
    def summary_dir(self) -> Path:
        return self.root / "summaries"

    @property
    def log_dir(self) -> Path:
        return self.root / "logs"

    def ensure(self) -> None:
        """Create every subdirectory. Idempotent."""
        for d in (self.root, self.iq_dir, self.summary_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)

    def is_within(self, candidate: Path) -> bool:
        """True iff *candidate* resolves to a path under ``self.root``.

        Uses ``Path.resolve()`` to defeat ``..`` traversal. Callers pass an
        absolute or relative path; both are handled.
        """
        try:
            resolved = candidate.resolve(strict=False)
            root_resolved = self.root.resolve(strict=False)
            resolved.relative_to(root_resolved)
            return True
        except (ValueError, OSError):
            return False

    def new_iq_path(self, prefix: str = "capture") -> Path:
        """Return a unique-per-call path under ``iq_dir``.

        Format: ``{prefix}-{unix_epoch_ms}-{uuid_hex[:6]}.iq``. Callers do
        NOT need to check for collision — the (ms + uuid suffix) combination
        makes clashes vanishingly unlikely.
        """
        stem = f"{prefix}-{int(time.time() * 1000)}-{uuid4().hex[:6]}.iq"
        return self.iq_dir / stem


def new_session(base_dir: Path) -> SessionPaths:
    """Create a fresh session under *base_dir*.

    ``base_dir`` is typically ``~/.hackrf-agent/sessions``. The
    ``session_id`` is ISO timestamp + short uuid, filename-safe.
    Directories are created eagerly.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    session_id = f"{now}_{uuid4().hex[:6]}"
    paths = SessionPaths(session_id=session_id, root=base_dir / session_id)
    paths.ensure()
    return paths
