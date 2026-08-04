"""Structural comparison of audit rows against a committed golden snapshot.

Timestamps, UUIDs, IQ paths, and durations vary run-to-run — the snapshot
helper masks them. Value assertions belong in unit tests, not the snapshot.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hackrf_agent.domain.audit_service import AuditRow


def rows_to_snapshot(rows: list[AuditRow]) -> list[dict[str, Any]]:
    """Convert audit rows to a structural snapshot dict.

    Drops: timestamps, trace_ids, session_ids, duration_ms, payload_json.
    Keeps: event, action, risk_level, blocked_reason (presence only).
    """
    snap: list[dict[str, Any]] = []
    for r in rows:
        snap.append(
            {
                "event": r.event.value,
                "action": r.action.value if r.action else None,
                "risk_level": r.risk_level.value if r.risk_level else None,
                "blocked_reason_present": r.blocked_reason is not None,
            }
        )
    return snap


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_snapshot(path: Path, snapshot: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_snapshot_matches(
    rows: list[AuditRow],
    snapshot_path: Path,
    *,
    update: bool = False,
) -> None:
    """Assert the row sequence matches the snapshot at ``snapshot_path``.

    If ``update=True`` (or env var ``UPDATE_SNAPSHOTS=1``), rewrite the
    snapshot file instead of asserting. This is the golden-master
    update path — commit the diff, review it as part of the PR.
    """
    actual = rows_to_snapshot(rows)
    if update or os.environ.get("UPDATE_SNAPSHOTS") == "1":
        save_snapshot(snapshot_path, actual)
        return
    expected = load_snapshot(snapshot_path)
    assert actual == expected, (
        f"audit snapshot mismatch at {snapshot_path}\n"
        f"expected: {expected}\n"
        f"actual:   {actual}\n"
        f"(rerun with UPDATE_SNAPSHOTS=1 to accept)"
    )
