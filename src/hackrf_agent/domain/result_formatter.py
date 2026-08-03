"""Per-action rules that turn raw driver return values into compact JSON-serializable dicts.

The last line of defense against raw IQ leaking into the LLM context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from hackrf_agent.domain.models import DeviceInfo
from hackrf_agent.domain.session import SessionPaths
from hackrf_agent.hw.dsp import (
    Peak,
    estimate_noise_floor,
    fft_freq_axis,
    fft_magnitude_db,
    find_peaks,
    iq_to_complex64,
)


class ResultFormatter:
    """Format raw handler return values into JSON-serializable dicts.

    One method per action. Every method returns a ``dict[str, Any]`` whose
    values are JSON-primitive (int, float, str, bool, None, list of same,
    dict of same). Never returns ndarray, bytes, complex, or Path (paths
    are stringified).
    """

    # -- action-specific formatters -----------------------------------------

    def format_device_info(self, info: DeviceInfo) -> dict[str, Any]:
        return {
            "serial": info.serial,
            "firmware_version": info.firmware_version,
            "board_revision": info.board_revision,
            "part_id": info.part_id,
        }

    def format_sweep(
        self,
        *,
        magnitude_db: npt.NDArray[np.float32],
        freqs_hz: npt.NDArray[np.float64],
        start_hz: int,
        stop_hz: int,
        top_n: int = 5,
    ) -> dict[str, Any]:
        peaks = find_peaks(magnitude_db, freqs_hz, top_n=top_n)
        noise = estimate_noise_floor(magnitude_db)
        return {
            "start_hz": int(start_hz),
            "stop_hz": int(stop_hz),
            "num_bins": int(magnitude_db.size),
            "noise_floor_dbfs": float(noise),
            "peaks": [self._peak_to_dict(p) for p in peaks],
        }

    def format_capture(
        self,
        *,
        iq_path: Path,
        center_hz: int,
        sample_rate_hz: int,
        num_samples: int,
        session_paths: SessionPaths,
    ) -> dict[str, Any]:
        """Load the just-written IQ, produce a summary. Path stays a string.

        Reads the IQ file back to run one FFT for the summary. This is
        deliberate: keeps the driver simple (it just writes bytes) and puts
        DSP consolidation here. Cost is one extra read of a small file.
        """
        if not session_paths.is_within(iq_path):
            raise ValueError(
                f"iq_path {iq_path} escapes session root {session_paths.root}"
            )
        raw = iq_path.read_bytes()
        iq = iq_to_complex64(raw)
        # Use a modest FFT size — enough for a summary, not the full capture.
        fft_size = min(4096, 1 << (iq.size.bit_length() - 1))
        if fft_size < 64:
            # Not enough samples for a meaningful FFT — return skeleton.
            return {
                "iq_path": str(iq_path),
                "center_hz": int(center_hz),
                "sample_rate_hz": int(sample_rate_hz),
                "num_samples": int(num_samples),
                "noise_floor_dbfs": None,
                "peaks": [],
                "note": "capture too short for spectral summary",
            }
        spec = fft_magnitude_db(iq, fft_size)
        freqs = fft_freq_axis(center_hz, sample_rate_hz, fft_size)
        peaks = find_peaks(spec, freqs, top_n=5)
        noise = estimate_noise_floor(spec)
        return {
            "iq_path": str(iq_path),
            "center_hz": int(center_hz),
            "sample_rate_hz": int(sample_rate_hz),
            "num_samples": int(num_samples),
            "noise_floor_dbfs": float(noise),
            "peaks": [self._peak_to_dict(p) for p in peaks],
        }

    def format_transmit(
        self,
        *,
        center_hz: int,
        sample_rate_hz: int,
        iq_path: Path,
        txvga_gain_db: int,
        duration_s: float,
    ) -> dict[str, Any]:
        return {
            "center_hz": int(center_hz),
            "sample_rate_hz": int(sample_rate_hz),
            "iq_path": str(iq_path),
            "txvga_gain_db": int(txvga_gain_db),
            "duration_s": float(duration_s),
        }

    def format_read_iq_summary(
        self,
        *,
        iq_path: Path,
        center_hz: int,
        sample_rate_hz: int,
        session_paths: SessionPaths,
    ) -> dict[str, Any]:
        # Same computation as format_capture, but the caller supplies the
        # path (must already exist and pass the safety check).
        return self.format_capture(
            iq_path=iq_path,
            center_hz=center_hz,
            sample_rate_hz=sample_rate_hz,
            num_samples=iq_path.stat().st_size // 2,
            session_paths=session_paths,
        )

    def format_decode_ook(
        self,
        *,
        iq_path: Path,
        note: str = "OOK decoding not yet implemented",
    ) -> dict[str, Any]:
        # Placeholder for Part 5 — decode_ook is a future action; the
        # executor still needs a formatter to return something structured.
        return {
            "iq_path": str(iq_path),
            "bits": [],
            "note": note,
        }

    def format_grant_list(self, grants: list[Any]) -> dict[str, Any]:
        # `grants` is a list of hackrf_agent.domain.models.Grant.
        return {
            "count": len(grants),
            "grants": [
                {
                    "id": str(g.id),
                    "kind": g.kind,
                    "band_start_hz": int(g.band_start_hz),
                    "band_stop_hz": int(g.band_stop_hz),
                    "max_gain_db": int(g.max_gain_db),
                    "granted_at": g.granted_at.isoformat(),
                    "expires_at": g.expires_at.isoformat(),
                }
                for g in grants
            ],
        }

    def format_audit_query(self, rows: list[Any]) -> dict[str, Any]:
        # `rows` is a list of hackrf_agent.domain.audit_service.AuditRow.
        return {
            "count": len(rows),
            "rows": [
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
            ],
        }

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _peak_to_dict(p: Peak) -> dict[str, Any]:
        return {
            "freq_hz": float(p.freq_hz),
            "power_dbfs": float(p.power_dbfs),
            "prominence_db": float(p.prominence_db),
            "bin_index": int(p.bin_index),
        }
