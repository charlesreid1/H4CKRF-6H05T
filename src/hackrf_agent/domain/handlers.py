"""One ``async`` callable per ``CommandAction``.

Each handler takes a shared context object plus the command's raw ``args``,
validates them against the typed args model, dispatches to the appropriate
driver (or service) method, and returns a formatter-ready payload.

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

from hackrf_agent.domain.args import (
    AuditQueryArgs,
    CaptureIqArgs,
    DecodeOokArgs,
    GetDeviceInfoArgs,
    GrantListArgs,
    ReadIqSummaryArgs,
    SweepSpectrumArgs,
    TransmitIqArgs,
)
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
    _parsed = GetDeviceInfoArgs(**args)
    info = await ctx.driver.get_device_info()
    return {"kind": "device_info", "info": info}


async def _handle_sweep_spectrum(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = SweepSpectrumArgs(**args)
    spec, freqs = await ctx.driver.sweep_spectrum(
        start_hz=parsed.start_freq_hz,
        stop_hz=parsed.end_freq_hz,
        sample_rate_hz=parsed.sample_rate_hz,
        lna_gain_db=parsed.lna_gain_db,
        vga_gain_db=parsed.vga_gain_db,
        rf_amp_db=parsed.rf_amp_db,
        dwell_s=parsed.dwell_s,
        fft_size=parsed.fft_size,
    )
    return {
        "kind": "sweep",
        "magnitude_db": spec,
        "freqs_hz": freqs,
        "start_hz": parsed.start_freq_hz,
        "stop_hz": parsed.end_freq_hz,
    }


async def _handle_capture_iq(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = CaptureIqArgs(**args)
    num_samples = int(parsed.sample_rate_hz * parsed.duration_s)
    out_path = ctx.session_paths.new_iq_path("capture")
    written = await ctx.driver.capture_iq(
        center_hz=parsed.center_freq_hz,
        sample_rate_hz=parsed.sample_rate_hz,
        num_samples=num_samples,
        lna_gain_db=parsed.lna_gain_db,
        vga_gain_db=parsed.vga_gain_db,
        rf_amp_db=parsed.rf_amp_db,
        out_path=out_path,
    )
    return {
        "kind": "capture",
        "iq_path": written,
        "center_hz": parsed.center_freq_hz,
        "sample_rate_hz": parsed.sample_rate_hz,
        "num_samples": num_samples,
    }


async def _handle_transmit_iq(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = TransmitIqArgs(**args)
    iq_path = parsed.iq_path_resolved
    # Safety re-check: iq_path must be under session root.
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    if not iq_path.is_file():
        raise ValueError(f"iq_path {iq_path} does not exist or is not a file")
    t0 = _time.perf_counter()
    await ctx.driver.transmit_iq(
        center_hz=parsed.center_freq_hz,
        sample_rate_hz=parsed.sample_rate_hz,
        iq_path=iq_path,
        txvga_gain_db=parsed.tx_vga_gain_db,
        rf_amp_db=parsed.rf_amp_db,
    )
    duration_s = _time.perf_counter() - t0
    return {
        "kind": "transmit",
        "center_hz": parsed.center_freq_hz,
        "sample_rate_hz": parsed.sample_rate_hz,
        "iq_path": iq_path,
        "txvga_gain_db": parsed.tx_vga_gain_db,
        "duration_s": duration_s,
    }


async def _handle_read_iq_summary(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = ReadIqSummaryArgs(**args)
    iq_path = parsed.iq_path_resolved
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    if not iq_path.is_file():
        raise ValueError(f"iq_path {iq_path} does not exist")
    return {
        "kind": "read_iq_summary",
        "iq_path": iq_path,
        "center_hz": parsed.center_freq_hz,
        "sample_rate_hz": parsed.sample_rate_hz,
    }


async def _handle_decode_ook(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = DecodeOokArgs(**args)
    iq_path = parsed.iq_path_resolved
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(f"iq_path {iq_path} escapes session root {ctx.session_paths.root}")
    return {"kind": "decode_ook", "iq_path": iq_path}


async def _handle_grant_list(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    _parsed = GrantListArgs(**args)
    grants = await ctx.permissions.list_active()
    return {"kind": "grant_list", "grants": grants}


async def _handle_audit_query(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = AuditQueryArgs(**args)
    rows = await ctx.audit.query(session_id=parsed.session_id, limit=parsed.limit)
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
