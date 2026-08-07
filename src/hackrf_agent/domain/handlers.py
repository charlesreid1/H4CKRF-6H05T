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
    AnalyzeIqCarrierFrequencyArgs,
    AnalyzeIqModulationArgs,
    AnalyzeIqSpectrogramArgs,
    AnalyzeIqSymbolsArgs,
    AuditQueryArgs,
    CaptureIqArgs,
    DecodeAdsBArgs,
    DecodeAprsArgs,
    DecodeAx25Args,
    DecodeManchesterArgs,
    DecodeNrzArgs,
    DecodeOokArgs,
    DecodePocsagArgs,
    DecodePpmArgs,
    DecodePwmArgs,
    DecodeRttyArgs,
    GetDeviceInfoArgs,
    GrantListArgs,
    KnowledgeBibliographyArgs,
    KnowledgeCrossReferenceArgs,
    KnowledgeExplainSignalArgs,
    KnowledgeListTopicsArgs,
    KnowledgeLookupBandArgs,
    KnowledgeLookupDecoderArgs,
    KnowledgeLookupKeyfobArgs,
    KnowledgeLookupModulationArgs,
    KnowledgeLookupProtocolArgs,
    KnowledgeRandomArgs,
    KnowledgeReadArgs,
    KnowledgeSearchArgs,
    KnowledgeVerifyClaimArgs,
    ReadIqSummaryArgs,
    SweepSpectrumArgs,
    TransmitIqArgs,
)
from hackrf_agent.domain.audit_service import AuditService
from hackrf_agent.domain.knowledge import (
    default_paths as _default_knowledge_paths,
)
from hackrf_agent.hw.analysis import (
    classify_modulation as _classify_modulation,
)
from hackrf_agent.hw.analysis import (
    estimate_carrier_frequency as _estimate_carrier_frequency,
)
from hackrf_agent.hw.analysis import (
    decode_ads_b as _decode_ads_b,
)
from hackrf_agent.hw.analysis import (
    decode_aprs as _decode_aprs,
)
from hackrf_agent.hw.analysis import (
    decode_ax25 as _decode_ax25,
)
from hackrf_agent.hw.analysis import (
    decode_manchester as _decode_manchester,
)
from hackrf_agent.hw.analysis import (
    decode_nrz as _decode_nrz,
)
from hackrf_agent.hw.analysis import (
    decode_nrzi as _decode_nrzi,
)
from hackrf_agent.hw.analysis import (
    decode_ppm as _decode_ppm,
)
from hackrf_agent.hw.analysis import (
    decode_pocsag as _decode_pocsag,
)
from hackrf_agent.hw.analysis import (
    decode_pwm as _decode_pwm,
)
from hackrf_agent.hw.analysis import (
    decode_rtty as _decode_rtty,
)
from hackrf_agent.hw.analysis import (
    estimate_symbol_rate as _estimate_symbol_rate,
)
from hackrf_agent.hw.analysis import (
    load_iq_file as _load_iq_file,
)
from hackrf_agent.hw.analysis import (
    spectrogram_summary as _spectrogram_summary,
)
from hackrf_agent.domain.knowledge import (
    cross_reference as _knowledge_cross_reference,
)
from hackrf_agent.domain.knowledge import (
    explain_signal as _knowledge_explain_signal,
)
from hackrf_agent.domain.knowledge import (
    get_bibliography as _knowledge_get_bibliography,
)
from hackrf_agent.domain.knowledge import (
    list_topics as _knowledge_list_topics,
)
from hackrf_agent.domain.knowledge import (
    lookup_band as _knowledge_lookup_band,
)
from hackrf_agent.domain.knowledge import (
    lookup_decoder as _knowledge_lookup_decoder,
)
from hackrf_agent.domain.knowledge import (
    lookup_keyfob as _knowledge_lookup_keyfob,
)
from hackrf_agent.domain.knowledge import (
    lookup_modulation as _knowledge_lookup_modulation,
)
from hackrf_agent.domain.knowledge import (
    lookup_protocol as _knowledge_lookup_protocol,
)
from hackrf_agent.domain.knowledge import (
    random_file as _knowledge_random_file,
)
from hackrf_agent.domain.knowledge import (
    read_file as _knowledge_read_file,
)
from hackrf_agent.domain.knowledge import (
    search as _knowledge_search,
)
from hackrf_agent.domain.knowledge import (
    verify_claim as _knowledge_verify_claim,
)
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
        "sample_rate_hz": parsed.sample_rate_hz,
        "fft_size": parsed.fft_size,
    }


async def _handle_capture_iq(ctx: HandlerContext, args: dict[str, Any]) -> dict[str, Any]:
    parsed = CaptureIqArgs(**args)
    if parsed.center_freq_hz is not None:
        effective_center_hz = parsed.center_freq_hz
    else:
        assert parsed.target_freq_hz is not None  # validator guarantees this
        # Offset the tuner by sample_rate/4 so DC lands a quarter of the
        # RX bandwidth away from the target. This keeps target inside the
        # passband while pushing the LO spike into a different bin.
        offset_hz = parsed.sample_rate_hz // 4
        effective_center_hz = parsed.target_freq_hz + offset_hz
    num_samples = int(parsed.sample_rate_hz * parsed.duration_s)
    out_path = ctx.session_paths.new_iq_path("capture")
    written = await ctx.driver.capture_iq(
        center_hz=effective_center_hz,
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
        "center_hz": effective_center_hz,
        "target_hz": parsed.target_freq_hz,  # None if caller used center_freq_hz
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
# Analysis-tier handlers — offline DSP on already-captured .iq files.
#
# Every handler here rejects paths that escape the session root (same rule
# transmit_iq enforces) and rejects files that don't exist. None of them
# touches libhackrf; the DSP primitives live in hackrf_agent.hw.analysis
# and use only NumPy.
# ---------------------------------------------------------------------------


def _resolve_iq_path(ctx: HandlerContext, iq_path_str: str) -> Path:
    """Resolve and validate an iq_path argument for analysis handlers."""
    iq_path = Path(iq_path_str)
    if not ctx.session_paths.is_within(iq_path):
        raise ValueError(
            f"iq_path {iq_path} escapes session root {ctx.session_paths.root}"
        )
    if not iq_path.is_file():
        raise ValueError(f"iq_path {iq_path} does not exist or is not a file")
    return iq_path


async def _handle_analyze_iq_modulation(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = AnalyzeIqModulationArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    candidates = _classify_modulation(iq)
    return {
        "kind": "analyze_iq_modulation",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        "num_samples": int(iq.size),
        "candidates": [
            {"family": c.family, "confidence": c.confidence, "note": c.note}
            for c in candidates
        ],
    }


async def _handle_analyze_iq_symbols(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = AnalyzeIqSymbolsArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _estimate_symbol_rate(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        min_rate_hz=parsed.min_rate_hz,
        max_rate_hz=parsed.max_rate_hz,
    )
    return {
        "kind": "analyze_iq_symbols",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        "num_samples": int(iq.size),
        **result,
    }


async def _handle_analyze_iq_carrier_frequency(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = AnalyzeIqCarrierFrequencyArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _estimate_carrier_frequency(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        fft_size=parsed.fft_size,
    )
    return {
        "kind": "analyze_iq_carrier_frequency",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        "num_samples": int(iq.size),
        **result,
    }


async def _handle_analyze_iq_spectrogram(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = AnalyzeIqSpectrogramArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    summary = _spectrogram_summary(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        fft_size=parsed.fft_size,
        overlap=parsed.overlap,
        max_slices=parsed.max_slices,
    )
    return {
        "kind": "analyze_iq_spectrogram",
        "iq_path": str(iq_path),
        "num_samples": int(iq.size),
        **summary,
    }


async def _handle_decode_manchester(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeManchesterArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_manchester(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        symbol_rate_hz=parsed.symbol_rate_hz,
        polarity=parsed.polarity,
    )
    return {
        "kind": "decode_manchester",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        "symbol_rate_hz": parsed.symbol_rate_hz,
        **result,
    }


async def _handle_decode_pwm(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodePwmArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_pwm(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        short_us=parsed.short_us,
        long_us=parsed.long_us,
    )
    return {
        "kind": "decode_pwm",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        **result,
    }


async def _handle_decode_ppm(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodePpmArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_ppm(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        pulse_us=parsed.pulse_us,
    )
    return {
        "kind": "decode_ppm",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        **result,
    }


async def _handle_decode_pocsag(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodePocsagArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_pocsag(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        baud=parsed.baud,
    )
    return {
        "kind": "decode_pocsag",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        **result,
    }


async def _handle_decode_ads_b(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeAdsBArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_ads_b(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        max_frames=parsed.max_frames,
    )
    return {
        "kind": "decode_ads_b",
        "iq_path": str(iq_path),
        **result,
    }


async def _handle_decode_rtty(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeRttyArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_rtty(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        baud=parsed.baud,
        invert=parsed.invert,
    )
    return {
        "kind": "decode_rtty",
        "iq_path": str(iq_path),
        **result,
    }


async def _handle_decode_ax25(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeAx25Args(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_ax25(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        baud=parsed.baud,
        invert=parsed.invert,
    )
    return {
        "kind": "decode_ax25",
        "iq_path": str(iq_path),
        **result,
    }


async def _handle_decode_aprs(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeAprsArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    result = _decode_aprs(
        iq,
        sample_rate_hz=parsed.sample_rate_hz,
        baud=parsed.baud,
        invert=parsed.invert,
    )
    return {
        "kind": "decode_aprs",
        "iq_path": str(iq_path),
        **result,
    }


async def _handle_decode_nrz(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = DecodeNrzArgs(**args)
    iq_path = _resolve_iq_path(ctx, parsed.iq_path)
    iq = _load_iq_file(iq_path)
    if parsed.variant == "nrz":
        result = _decode_nrz(
            iq,
            sample_rate_hz=parsed.sample_rate_hz,
            symbol_rate_hz=parsed.symbol_rate_hz,
            inverted=parsed.inverted,
        )
    else:
        result = _decode_nrzi(
            iq,
            sample_rate_hz=parsed.sample_rate_hz,
            symbol_rate_hz=parsed.symbol_rate_hz,
        )
    return {
        "kind": "decode_nrz",
        "iq_path": str(iq_path),
        "sample_rate_hz": parsed.sample_rate_hz,
        "symbol_rate_hz": parsed.symbol_rate_hz,
        "variant": parsed.variant,
        **result,
    }


# ---------------------------------------------------------------------------
# Knowledge-tier handlers — read-only corpus access.
#
# All six route through hackrf_agent.domain.knowledge, which enforces path
# traversal and file-size limits at the boundary. None of them touch
# libhackrf, capture IQ, or open a driver handle. RiskAssessor classifies
# every one as hardcoded LOW.
# ---------------------------------------------------------------------------


async def _handle_knowledge_list_topics(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    _parsed = KnowledgeListTopicsArgs(**args)
    paths = _default_knowledge_paths()
    topics = _knowledge_list_topics(paths)
    return {"kind": "knowledge_list_topics", "topics": topics}


async def _handle_knowledge_read(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeReadArgs(**args)
    paths = _default_knowledge_paths()
    payload = _knowledge_read_file(paths, parsed.topic, parsed.name)
    return {"kind": "knowledge_read", **payload}


async def _handle_knowledge_search(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeSearchArgs(**args)
    paths = _default_knowledge_paths()
    hits = _knowledge_search(paths, parsed.query, max_results=parsed.max_results)
    return {
        "kind": "knowledge_search",
        "query": parsed.query,
        "max_results": parsed.max_results,
        "hits": hits,
        "truncated": len(hits) >= parsed.max_results,
    }


async def _handle_knowledge_lookup_band(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeLookupBandArgs(**args)
    paths = _default_knowledge_paths()
    matches = _knowledge_lookup_band(paths, parsed.freq_hz)
    return {
        "kind": "knowledge_lookup_band",
        "freq_hz": parsed.freq_hz,
        "matches": matches,
    }


async def _handle_knowledge_lookup_modulation(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeLookupModulationArgs(**args)
    paths = _default_knowledge_paths()
    record = _knowledge_lookup_modulation(paths, parsed.name)
    return {
        "kind": "knowledge_lookup_modulation",
        "name": parsed.name,
        "record": record,
    }


async def _handle_knowledge_lookup_protocol(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeLookupProtocolArgs(**args)
    paths = _default_knowledge_paths()
    record = _knowledge_lookup_protocol(paths, parsed.name)
    return {
        "kind": "knowledge_lookup_protocol",
        "name": parsed.name,
        "record": record,
    }


async def _handle_knowledge_lookup_keyfob(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeLookupKeyfobArgs(**args)
    paths = _default_knowledge_paths()
    matches = _knowledge_lookup_keyfob(paths, parsed.vendor, parsed.model)
    return {
        "kind": "knowledge_lookup_keyfob",
        "vendor": parsed.vendor,
        "model": parsed.model,
        "matches": matches,
    }


async def _handle_knowledge_lookup_decoder(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeLookupDecoderArgs(**args)
    paths = _default_knowledge_paths()
    record = _knowledge_lookup_decoder(paths, parsed.name)
    return {
        "kind": "knowledge_lookup_decoder",
        "name": parsed.name,
        "record": record,
    }


async def _handle_knowledge_bibliography(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeBibliographyArgs(**args)
    paths = _default_knowledge_paths()
    records = _knowledge_get_bibliography(paths, parsed.cite_id)
    return {
        "kind": "knowledge_bibliography",
        "cite_id": parsed.cite_id,
        "records": records,
    }


async def _handle_knowledge_random(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeRandomArgs(**args)
    paths = _default_knowledge_paths()
    payload = _knowledge_random_file(paths, seed=parsed.seed)
    return {"kind": "knowledge_random", **payload}


async def _handle_knowledge_explain_signal(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeExplainSignalArgs(**args)
    paths = _default_knowledge_paths()
    candidates = _knowledge_explain_signal(
        paths,
        freq_hz=parsed.freq_hz,
        bw_hz=parsed.bw_hz,
        modulation_guess=parsed.modulation_guess,
        max_results=parsed.max_results,
    )
    return {
        "kind": "knowledge_explain_signal",
        "freq_hz": parsed.freq_hz,
        "bw_hz": parsed.bw_hz,
        "modulation_guess": parsed.modulation_guess,
        "candidates": candidates,
    }


async def _handle_knowledge_cross_reference(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeCrossReferenceArgs(**args)
    paths = _default_knowledge_paths()
    result = _knowledge_cross_reference(paths, parsed.record_id)
    return {
        "kind": "knowledge_cross_reference",
        "record_id": parsed.record_id,
        **result,
    }


async def _handle_knowledge_verify_claim(
    ctx: HandlerContext, args: dict[str, Any]
) -> dict[str, Any]:
    parsed = KnowledgeVerifyClaimArgs(**args)
    verdict = _knowledge_verify_claim(parsed.text)
    return {
        "kind": "knowledge_verify_claim",
        "text": parsed.text,
        **verdict,
    }


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
    CommandAction.KNOWLEDGE_LIST_TOPICS: _handle_knowledge_list_topics,
    CommandAction.KNOWLEDGE_READ: _handle_knowledge_read,
    CommandAction.KNOWLEDGE_SEARCH: _handle_knowledge_search,
    CommandAction.KNOWLEDGE_LOOKUP_BAND: _handle_knowledge_lookup_band,
    CommandAction.KNOWLEDGE_LOOKUP_MODULATION: _handle_knowledge_lookup_modulation,
    CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL: _handle_knowledge_lookup_protocol,
    CommandAction.KNOWLEDGE_LOOKUP_KEYFOB: _handle_knowledge_lookup_keyfob,
    CommandAction.KNOWLEDGE_LOOKUP_DECODER: _handle_knowledge_lookup_decoder,
    CommandAction.KNOWLEDGE_BIBLIOGRAPHY: _handle_knowledge_bibliography,
    CommandAction.KNOWLEDGE_RANDOM: _handle_knowledge_random,
    CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL: _handle_knowledge_explain_signal,
    CommandAction.KNOWLEDGE_CROSS_REFERENCE: _handle_knowledge_cross_reference,
    CommandAction.KNOWLEDGE_VERIFY_CLAIM: _handle_knowledge_verify_claim,
    CommandAction.ANALYZE_IQ_MODULATION: _handle_analyze_iq_modulation,
    CommandAction.ANALYZE_IQ_SYMBOLS: _handle_analyze_iq_symbols,
    CommandAction.ANALYZE_IQ_SPECTROGRAM: _handle_analyze_iq_spectrogram,
    CommandAction.ANALYZE_IQ_CARRIER_FREQUENCY: _handle_analyze_iq_carrier_frequency,
    CommandAction.DECODE_MANCHESTER: _handle_decode_manchester,
    CommandAction.DECODE_PWM: _handle_decode_pwm,
    CommandAction.DECODE_PPM: _handle_decode_ppm,
    CommandAction.DECODE_NRZ: _handle_decode_nrz,
    CommandAction.DECODE_POCSAG: _handle_decode_pocsag,
    CommandAction.DECODE_ADS_B: _handle_decode_ads_b,
    CommandAction.DECODE_RTTY: _handle_decode_rtty,
    CommandAction.DECODE_AX25: _handle_decode_ax25,
    CommandAction.DECODE_APRS: _handle_decode_aprs,
}
