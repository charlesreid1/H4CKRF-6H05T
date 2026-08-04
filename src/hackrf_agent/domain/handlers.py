"""One ``async`` callable per ``CommandAction``.

Each handler takes a shared context object plus the command's raw ``args``,
dispatches to the appropriate driver (or service) method, and returns a
formatter-ready payload.

Handlers do NOT format results themselves — that's the executor's next
step. Handlers also do NOT touch the audit log. Separation keeps them
unit-testable with a mocked driver and nothing else.
"""

from __future__ import annotations

import time as _time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.models import CommandAction, DeviceInfo
from hackrf_agent.domain.permission_service import PermissionService
from hackrf_agent.domain.session import SessionPaths


class DriverProtocol(Protocol):
    """Minimal surface of HackrfDriver the executor cares about.

    Documented as a Protocol so tests can pass a plain mock without needing
    to satisfy HackrfDriver's async-context-manager contract. Production
    callers pass the real HackrfDriver.
    """

    async def get_device_info(self) -> DeviceInfo: ...

    async def sweep_spectrum(
        self,
        *,
        start_hz: int,
        stop_hz: int,
        sample_rate_hz: int,
        lna_gain_db: int = ...,
        vga_gain_db: int = ...,
        rf_amp_db: int = ...,
        dwell_s: float = ...,
        fft_size: int = ...,
    ) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.float64]]: ...

    async def capture_iq(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        num_samples: int,
        lna_gain_db: int = ...,
        vga_gain_db: int = ...,
        rf_amp_db: int = ...,
        out_path: Path,
    ) -> Path: ...

    async def transmit_iq(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        iq_path: Path,
        txvga_gain_db: int,
        rf_amp_db: int = ...,
    ) -> None: ...


@dataclass(frozen=True)
class HandlerContext:
    """Shared per-command dependencies the handlers reach for."""

    driver: DriverProtocol
    permissions: PermissionService
    audit: AuditService
    session_paths: SessionPaths


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_get_device_info(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    info = await ctx.driver.get_device_info()
    return {"kind": "device_info", "info": info}


async def _handle_sweep_spectrum(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    start_hz = int(args["start_freq_hz"])
    stop_hz = int(args["end_freq_hz"])
    sample_rate_hz = int(args.get("sample_rate_hz", 2_000_000))
    lna_gain_db = int(args.get("lna_gain_db", 16))
    vga_gain_db = int(args.get("vga_gain_db", 20))
    rf_amp_db = int(args.get("rf_amp_db", 0))
    dwell_s = float(args.get("dwell_s", 1.0))
    fft_size = int(args.get("fft_size", 4096))
    spec, freqs = await ctx.driver.sweep_spectrum(
        start_hz=start_hz,
        stop_hz=stop_hz,
        sample_rate_hz=sample_rate_hz,
        lna_gain_db=lna_gain_db,
        vga_gain_db=vga_gain_db,
        rf_amp_db=rf_amp_db,
        dwell_s=dwell_s,
        fft_size=fft_size,
    )
    return {
        "kind": "sweep",
        "magnitude_db": spec,
        "freqs_hz": freqs,
        "start_hz": start_hz,
        "stop_hz": stop_hz,
    }


async def _handle_capture_iq(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    center_hz = int(args["center_freq_hz"])
    sample_rate_hz = int(args.get("sample_rate_hz", 2_000_000))
    duration_s = float(args["duration_s"])
    num_samples = int(sample_rate_hz * duration_s)
    lna_gain_db = int(args.get("lna_gain_db", 16))
    vga_gain_db = int(args.get("vga_gain_db", 20))
    rf_amp_db = int(args.get("rf_amp_db", 0))
    out_path = ctx.session_paths.new_iq_path("capture")
    written = await ctx.driver.capture_iq(
        center_hz=center_hz,
        sample_rate_hz=sample_rate_hz,
        num_samples=num_samples,
        lna_gain_db=lna_gain_db,
        vga_gain_db=vga_gain_db,
        rf_amp_db=rf_amp_db,
        out_path=out_path,
    )
    return {
        "kind": "capture",
        "iq_path": written,
        "center_hz": center_hz,
        "sample_rate_hz": sample_rate_hz,
        "num_samples": num_samples,
    }


async def _handle_transmit_iq(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    center_hz = int(args["center_freq_hz"])
    sample_rate_hz = int(args.get("sample_rate_hz", 2_000_000))
    txvga_gain_db = int(args["tx_vga_gain_db"])
    rf_amp_db = int(args.get("rf_amp_db", 0))
    iq_path = Path(args["iq_path"])
    # Safety re-check: iq_path must be under session root.
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    if not iq_path.is_file():
        raise ValueError(f"iq_path {iq_path} does not exist or is not a file")
    t0 = _time.perf_counter()
    await ctx.driver.transmit_iq(
        center_hz=center_hz,
        sample_rate_hz=sample_rate_hz,
        iq_path=iq_path,
        txvga_gain_db=txvga_gain_db,
        rf_amp_db=rf_amp_db,
    )
    duration_s = _time.perf_counter() - t0
    return {
        "kind": "transmit",
        "center_hz": center_hz,
        "sample_rate_hz": sample_rate_hz,
        "iq_path": iq_path,
        "txvga_gain_db": txvga_gain_db,
        "duration_s": duration_s,
    }


async def _handle_read_iq_summary(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    iq_path = Path(args["iq_path"])
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    if not iq_path.is_file():
        raise ValueError(f"iq_path {iq_path} does not exist")
    center_hz = int(args["center_freq_hz"])
    sample_rate_hz = int(args.get("sample_rate_hz", 2_000_000))
    return {
        "kind": "read_iq_summary",
        "iq_path": iq_path,
        "center_hz": center_hz,
        "sample_rate_hz": sample_rate_hz,
    }


async def _handle_decode_ook(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    iq_path = Path(args["iq_path"])
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    return {"kind": "decode_ook", "iq_path": iq_path}


async def _handle_grant_list(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    grants = await ctx.permissions.list_active()
    return {"kind": "grant_list", "grants": grants}


async def _handle_audit_query(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    session_id = args.get("session_id")
    limit = int(args.get("limit", 50))
    rows = await ctx.audit.query(session_id=session_id, limit=limit)
    return {"kind": "audit_query", "rows": rows}


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS: dict[
    CommandAction,
    Callable[[HandlerContext, dict[str, Any]], Awaitable[dict[str, Any]]],
] = {
    CommandAction.GET_DEVICE_INFO: _handle_get_device_info,
    CommandAction.SWEEP_SPECTRUM: _handle_sweep_spectrum,
    CommandAction.CAPTURE_IQ: _handle_capture_iq,
    CommandAction.TRANSMIT_IQ: _handle_transmit_iq,
    CommandAction.READ_IQ_SUMMARY: _handle_read_iq_summary,
    CommandAction.DECODE_OOK: _handle_decode_ook,
    CommandAction.GRANT_LIST: _handle_grant_list,
    CommandAction.AUDIT_QUERY: _handle_audit_query,
}
