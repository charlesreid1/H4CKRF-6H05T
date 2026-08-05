"""MCP resources exposing audit log slices, active grants, and session info.

Each resource is backed by a domain service call. Resources are read-only
snapshots — they don't mutate state.

URI templates use ``hackrf://`` as the scheme to namespace resources under
the HackRF agent's domain.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.types import (
    ReadResourceResult,
    Resource,
    TextResourceContents,
)

from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.session import SessionPaths

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resource definitions
# ---------------------------------------------------------------------------


def list_resources(session_id: str) -> list[Resource]:
    """Return the static resource list.

    Dynamic resources (audit by session, etc.) are also listed here
    as URI templates where applicable.
    """
    return [
        Resource(
            name="Audit — recent",
            uri="hackrf://audit/recent?limit=50",
            description="Most recent audit events across all sessions.",
            mime_type="application/json",
        ),
        Resource(
            name="Audit — by session",
            uri=f"hackrf://audit/session/{session_id}",
            description=f"Audit events for session {session_id}.",
            mime_type="application/json",
        ),
        Resource(
            name="Grants — active",
            uri="hackrf://grants/active",
            description="Currently active TX grants.",
            mime_type="application/json",
        ),
        Resource(
            name="Grants — all",
            uri="hackrf://grants/all",
            description="All grants ever issued (including expired/revoked).",
            mime_type="application/json",
        ),
        Resource(
            name="Sessions — current",
            uri="hackrf://sessions/current",
            description="Metadata about the current MCP session.",
            mime_type="application/json",
        ),
    ]


# ---------------------------------------------------------------------------
# Resource reading
# ---------------------------------------------------------------------------


async def read_resource(
    uri: str,
    *,
    audit: AuditService,
    permissions: PermissionService,
    session_paths: SessionPaths,
    session_id: str,
) -> ReadResourceResult | None:
    """Read a resource by URI. Returns None for unknown URIs."""

    # --- audit/recent?limit=N ---
    if uri.startswith("hackrf://audit/recent"):
        limit = _parse_query_int(uri, "limit", 50)
        rows = await audit.query(limit=limit)
        return _json_result(uri, _format_audit_rows(rows))

    # --- audit/session/{id} ---
    if uri.startswith("hackrf://audit/session/"):
        sid = uri[len("hackrf://audit/session/"):].split("?")[0]
        rows = await audit.query(session_id=sid)
        return _json_result(uri, _format_audit_rows(rows))

    # --- grants/active ---
    if uri == "hackrf://grants/active":
        grants = await permissions.list_active()
        return _json_result(uri, _format_grants(grants))

    # --- grants/all ---
    if uri == "hackrf://grants/all":
        grants = await permissions.list_all()
        return _json_result(uri, _format_grants(grants))

    # --- sessions/current ---
    if uri == "hackrf://sessions/current":
        data = {
            "session_id": session_id,
            "root": str(session_paths.root),
            "iq_dir": str(session_paths.iq_dir),
            "summary_dir": str(session_paths.summary_dir),
        }
        return _json_result(uri, data)

    logger.warning("Unknown resource URI: %s", uri)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_result(uri: str, data: Any) -> ReadResourceResult:
    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri=uri,
                mime_type="application/json",
                text=json.dumps(data, indent=2, default=str),
            )
        ],
    )


def _parse_query_int(uri: str, key: str, default: int) -> int:
    """Parse a query parameter from a URI string. Returns *default* on failure."""
    try:
        query = uri.split("?", 1)[1] if "?" in uri else ""
        for part in query.split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k == key:
                return int(v)
    except (ValueError, IndexError):
        pass
    return default


def _format_audit_rows(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": int(r.id),
            "trace_id": str(r.trace_id),
            "session_id": r.session_id,
            "timestamp": float(r.timestamp),
            "event": r.event.value,
            "action": r.action.value if r.action else None,
            "risk_level": r.risk_level.value if r.risk_level else None,
            "blocked_reason": r.blocked_reason,
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]


def _format_grants(grants: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(g.id),
            "kind": g.kind,
            "band_start_hz": int(g.band_start_hz),
            "band_stop_hz": int(g.band_stop_hz),
            "max_gain_db": int(g.max_gain_db),
            "granted_at": g.granted_at.isoformat(),
            "expires_at": g.expires_at.isoformat(),
            "is_active": g.is_active,
        }
        for g in grants
    ]
