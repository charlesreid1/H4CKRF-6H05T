"""Deterministic risk-tier assignment.

Never calls the LLM. Never touches hardware. Never opens a file.
Given an ExecuteCommand and a snapshot of active grants, returns a
RiskAssessment. Pure function of inputs (module state aside).
"""

from typing import Any

from hackrf_agent.domain.frequency_policy import (
    is_blocked,
    is_in_amateur,
    is_in_ism,
)
from hackrf_agent.domain.models import (
    CommandAction,
    ExecuteCommand,
    Grant,
    RiskAssessment,
    RiskLevel,
)


class RiskAssessor:
    """Deterministic risk-tier assignment.

    Never calls the LLM. Never touches hardware. Never opens a file. Given
    an ExecuteCommand and a snapshot of active grants, returns a
    RiskAssessment. Pure function of inputs (module state aside).
    """

    # Gain caps — TX VGA
    MAX_TX_VGA_GAIN_DB = 47  # hardware maximum (libhackrf)
    MEDIUM_TX_VGA_GAIN_DB = 30  # policy cap for MEDIUM without a grant

    # Duration / dwell caps
    LOW_CAPTURE_DURATION_S = 5.0  # captures ≤ this stay LOW
    LOW_SWEEP_DWELL_S = 2.0  # sweeps ≤ this stay LOW

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def assess(
        self,
        command: ExecuteCommand,
        active_grants: list[Grant],
    ) -> RiskAssessment:
        """Return a RiskAssessment for *command* given the current grants."""
        action = command.action
        args = command.args

        # A. Read-only / always-LOW actions
        if action in (
            CommandAction.GET_DEVICE_INFO,
            CommandAction.GRANT_LIST,
            CommandAction.AUDIT_QUERY,
            CommandAction.READ_IQ_SUMMARY,
            CommandAction.DECODE_OOK,
            CommandAction.PLAY_SEQUENCE,
        ):
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="read-only administrative action",
                requires_confirmation=False,
            )

        # A2. Knowledge tier — read-only corpus access. Always LOW.
        # These handlers never touch libhackrf, never cause RF emission,
        # and never write to disk. Any TX-adjacent knowledge verb added
        # in the future must NOT be added here — it belongs in its own
        # tier assessment.
        if action in (
            CommandAction.KNOWLEDGE_LIST_TOPICS,
            CommandAction.KNOWLEDGE_READ,
            CommandAction.KNOWLEDGE_SEARCH,
            CommandAction.KNOWLEDGE_LOOKUP_BAND,
            CommandAction.KNOWLEDGE_LOOKUP_MODULATION,
            CommandAction.KNOWLEDGE_LOOKUP_PROTOCOL,
            CommandAction.KNOWLEDGE_LOOKUP_KEYFOB,
            CommandAction.KNOWLEDGE_LOOKUP_DECODER,
            CommandAction.KNOWLEDGE_BIBLIOGRAPHY,
            CommandAction.KNOWLEDGE_RANDOM,
            CommandAction.KNOWLEDGE_EXPLAIN_SIGNAL,
            CommandAction.KNOWLEDGE_CROSS_REFERENCE,
            CommandAction.KNOWLEDGE_VERIFY_CLAIM,
        ):
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="read-only knowledge-corpus access",
                requires_confirmation=False,
            )

        # A3. Analysis tier — offline DSP on already-captured .iq files.
        # Always LOW. Cannot touch libhackrf. Handlers enforce that the
        # iq_path is under the session root before opening.
        if action in (
            CommandAction.ANALYZE_IQ_MODULATION,
            CommandAction.ANALYZE_IQ_SYMBOLS,
            CommandAction.ANALYZE_IQ_SPECTROGRAM,
            CommandAction.ANALYZE_IQ_CARRIER_FREQUENCY,
            CommandAction.DECODE_MANCHESTER,
            CommandAction.DECODE_PWM,
            CommandAction.DECODE_PPM,
            CommandAction.DECODE_NRZ,
            CommandAction.DECODE_POCSAG,
            CommandAction.DECODE_ADS_B,
            CommandAction.DECODE_RTTY,
            CommandAction.DECODE_AX25,
            CommandAction.DECODE_APRS,
        ):
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="offline IQ analysis; reads from session dir only",
                requires_confirmation=False,
            )

        # B. SWEEP_SPECTRUM
        if action == CommandAction.SWEEP_SPECTRUM:
            return self._assess_sweep(args)

        # B2. SWEEP_SPECTRUM_BULK — per-range dwell rules; any BLOCKED
        # range in the list blocks the whole call.
        if action == CommandAction.SWEEP_SPECTRUM_BULK:
            return self._assess_sweep_bulk(args)

        # C. CAPTURE_IQ
        if action == CommandAction.CAPTURE_IQ:
            return self._assess_capture_iq(args)

        # D. TRANSMIT_IQ
        if action == CommandAction.TRANSMIT_IQ:
            return self._assess_transmit_iq(args, active_grants)

        # E. Unknown action (defensive — shouldn't be reachable)
        return RiskAssessment(
            level=RiskLevel.BLOCKED,
            reason="unknown action",
            blocked_reason="unknown action",
            requires_confirmation=False,
        )

    # ------------------------------------------------------------------
    # Args-extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_int(args: dict[str, Any], key: str) -> int | None:
        """Return args[key] as int, or None if missing / wrong type."""
        val = args.get(key)
        if isinstance(val, bool):  # bool is a subclass of int; reject it
            return None
        if isinstance(val, int):
            return val
        return None

    @staticmethod
    def _get_float(args: dict[str, Any], key: str) -> float | None:
        """Return args[key] as float, or None if missing / wrong type."""
        val = args.get(key)
        if isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        return None

    # ------------------------------------------------------------------
    # Per-action assessment helpers
    # ------------------------------------------------------------------

    def _assess_sweep(self, args: dict[str, Any]) -> RiskAssessment:
        start_hz = self._get_int(args, "start_freq_hz")
        if start_hz is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'start_freq_hz' missing or not an integer",
                requires_confirmation=False,
            )

        end_hz = self._get_int(args, "end_freq_hz")
        if end_hz is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'end_freq_hz' missing or not an integer",
                requires_confirmation=False,
            )

        if start_hz >= end_hz:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="invalid sweep range",
                blocked_reason="start_freq_hz must be less than end_freq_hz",
                requires_confirmation=False,
            )

        dwell_s = self._get_float(args, "dwell_s")
        if dwell_s is None:
            dwell_s = 1.0  # default, do NOT block

        if dwell_s <= self.LOW_SWEEP_DWELL_S:
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="short RX sweep",
                requires_confirmation=False,
            )

        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="long RX sweep (dwell > 2 s)",
            requires_confirmation=True,
        )

    def _assess_sweep_bulk(self, args: dict[str, Any]) -> RiskAssessment:
        ranges = args.get("ranges")
        if not isinstance(ranges, list) or len(ranges) < 2:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="invalid ranges argument",
                blocked_reason="sweep_spectrum_bulk needs a list of >=2 ranges",
                requires_confirmation=False,
            )
        # Any range with malformed bounds → BLOCKED.
        for r in ranges:
            if not isinstance(r, dict):
                return RiskAssessment(
                    level=RiskLevel.BLOCKED,
                    reason="malformed range entry",
                    blocked_reason="range entries must be objects",
                    requires_confirmation=False,
                )
            start = r.get("start_freq_hz")
            end = r.get("end_freq_hz")
            if not isinstance(start, int) or not isinstance(end, int):
                return RiskAssessment(
                    level=RiskLevel.BLOCKED,
                    reason="malformed range entry",
                    blocked_reason="each range needs integer start/end_freq_hz",
                    requires_confirmation=False,
                )
            if start >= end:
                return RiskAssessment(
                    level=RiskLevel.BLOCKED,
                    reason="malformed range entry",
                    blocked_reason=f"range [{start}..{end}] has start >= end",
                    requires_confirmation=False,
                )

        dwell_s = self._get_float(args, "dwell_s")
        if dwell_s is None:
            dwell_s = 1.0

        # LOW when short-dwell (≤ 2s per range); MEDIUM otherwise. The
        # aggregate wall-clock can still be long across many ranges,
        # but each range dispatches as an independent sub-sweep — that
        # is the parity we want with SWEEP_SPECTRUM.
        if dwell_s <= self.LOW_SWEEP_DWELL_S:
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="short-dwell bulk RX sweep",
                requires_confirmation=False,
            )
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="long-dwell bulk RX sweep (per-range dwell > 2 s)",
            requires_confirmation=True,
        )

    def _assess_capture_iq(self, args: dict[str, Any]) -> RiskAssessment:
        center_hz = self._get_int(args, "center_freq_hz")
        if center_hz is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'center_freq_hz' missing or not an integer",
                requires_confirmation=False,
            )

        duration_s = self._get_float(args, "duration_s")
        if duration_s is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'duration_s' missing or not a number",
                requires_confirmation=False,
            )

        if duration_s <= 0:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="invalid duration",
                blocked_reason="duration_s must be positive",
                requires_confirmation=False,
            )

        if duration_s <= self.LOW_CAPTURE_DURATION_S:
            return RiskAssessment(
                level=RiskLevel.LOW,
                reason="short RX capture",
                requires_confirmation=False,
            )

        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="long RX capture (duration > 5 s)",
            requires_confirmation=True,
        )

    def _assess_transmit_iq(
        self,
        args: dict[str, Any],
        active_grants: list[Grant],
    ) -> RiskAssessment:
        center_hz = self._get_int(args, "center_freq_hz")
        if center_hz is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'center_freq_hz' missing or not an integer",
                requires_confirmation=False,
            )

        gain_db = self._get_int(args, "tx_vga_gain_db")
        if gain_db is None:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="missing or malformed argument",
                blocked_reason="required arg 'tx_vga_gain_db' missing or not an integer",
                requires_confirmation=False,
            )

        # Hardware / arg sanity checks
        if gain_db > self.MAX_TX_VGA_GAIN_DB:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="TX VGA gain exceeds hardware maximum of 47 dB",
                blocked_reason="tx_vga_gain_db > 47",
                requires_confirmation=False,
            )

        if gain_db < 0:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason="negative TX gain",
                blocked_reason="tx_vga_gain_db < 0",
                requires_confirmation=False,
            )

        # Blocked band check
        blocked, reason = is_blocked(center_hz)
        if blocked:
            return RiskAssessment(
                level=RiskLevel.BLOCKED,
                reason=reason or "blocked band",
                blocked_reason=reason,
                requires_confirmation=False,
            )

        # Grant check — any active grant covering this TX → LOW (auto-execute)
        # The operator has already pre-authorized this band + gain via
        # `hackrf-agent grant tx ...`; no per-command approval needed.
        for grant in active_grants:
            if grant.covers_transmission(center_hz, gain_db):
                return RiskAssessment(
                    level=RiskLevel.LOW,
                    reason="in-scope grant covers this transmission",
                    requires_confirmation=False,
                )

        # ISM band rules
        in_ism, ism_label = is_in_ism(center_hz)
        if in_ism:
            if gain_db <= self.MEDIUM_TX_VGA_GAIN_DB:
                return RiskAssessment(
                    level=RiskLevel.MEDIUM,
                    reason=f"ISM band TX (gain ≤ {self.MEDIUM_TX_VGA_GAIN_DB} dB)",
                    requires_confirmation=True,
                )
            else:
                return RiskAssessment(
                    level=RiskLevel.HIGH,
                    reason="ISM band TX with gain > 30 dB",
                    requires_confirmation=True,
                )

        # Amateur band — HIGH (licensed-operator territory)
        in_amateur, amateur_label = is_in_amateur(center_hz)
        if in_amateur:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason="amateur band — licensed operator required",
                requires_confirmation=True,
            )

        # Unclassified frequency — HIGH
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="TX in unclassified band",
            requires_confirmation=True,
        )
