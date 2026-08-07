"""Data models and enums for the HackRF agent domain.

Every model here is pure data — zero I/O. Pydantic v2 throughout.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommandAction(str, Enum):  # noqa: UP042
    GET_DEVICE_INFO = "get_device_info"
    SWEEP_SPECTRUM = "sweep_spectrum"
    CAPTURE_IQ = "capture_iq"
    TRANSMIT_IQ = "transmit_iq"
    READ_IQ_SUMMARY = "read_iq_summary"
    DECODE_OOK = "decode_ook"
    GRANT_LIST = "grant_list"
    AUDIT_QUERY = "audit_query"
    # Analysis tier — offline DSP on already-captured .iq files.
    # Hardcoded LOW risk. Cannot touch libhackrf.
    ANALYZE_IQ_MODULATION = "analyze_iq_modulation"
    ANALYZE_IQ_SYMBOLS = "analyze_iq_symbols"
    ANALYZE_IQ_SPECTROGRAM = "analyze_iq_spectrogram"
    ANALYZE_IQ_CARRIER_FREQUENCY = "analyze_iq_carrier_frequency"
    DECODE_MANCHESTER = "decode_manchester"
    DECODE_PWM = "decode_pwm"
    DECODE_PPM = "decode_ppm"
    DECODE_NRZ = "decode_nrz"
    DECODE_POCSAG = "decode_pocsag"
    DECODE_ADS_B = "decode_ads_b"
    DECODE_RTTY = "decode_rtty"
    DECODE_AX25 = "decode_ax25"
    DECODE_APRS = "decode_aprs"
    # Knowledge tier — read-only corpus access. Hardcoded LOW risk.
    # See knowledge/ MANIFEST.md and plan-organization.md Phase 3.
    KNOWLEDGE_LIST_TOPICS = "knowledge_list_topics"
    KNOWLEDGE_READ = "knowledge_read"
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_LOOKUP_BAND = "knowledge_lookup_band"
    KNOWLEDGE_LOOKUP_MODULATION = "knowledge_lookup_modulation"
    KNOWLEDGE_LOOKUP_PROTOCOL = "knowledge_lookup_protocol"
    KNOWLEDGE_LOOKUP_KEYFOB = "knowledge_lookup_keyfob"
    KNOWLEDGE_LOOKUP_DECODER = "knowledge_lookup_decoder"
    KNOWLEDGE_BIBLIOGRAPHY = "knowledge_bibliography"
    KNOWLEDGE_RANDOM = "knowledge_random"
    KNOWLEDGE_EXPLAIN_SIGNAL = "knowledge_explain_signal"
    KNOWLEDGE_CROSS_REFERENCE = "knowledge_cross_reference"
    KNOWLEDGE_VERIFY_CLAIM = "knowledge_verify_claim"


class RiskLevel(str, Enum):  # noqa: UP042
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKED = "BLOCKED"


class AuditEventType(str, Enum):  # noqa: UP042
    COMMAND_RECEIVED = "COMMAND_RECEIVED"
    RISK_ASSESSED = "RISK_ASSESSED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_DENIED = "APPROVAL_DENIED"
    EXECUTED = "EXECUTED"
    RESULT = "RESULT"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Helper callables for default factories
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current UTC datetime, safe for Field(default_factory=…)."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Command models
# ---------------------------------------------------------------------------


class ExecuteCommand(BaseModel):
    action: CommandAction
    args: dict[str, Any] = Field(default_factory=dict)
    justification: str
    expected_effect: str

    @model_validator(mode="after")
    def _validate_string_fields(self) -> "ExecuteCommand":
        if not self.justification.strip():
            raise ValueError("justification must be non-empty")
        if not self.expected_effect.strip():
            raise ValueError("expected_effect must be non-empty")
        return self


class CommandResult(BaseModel):
    success: bool
    action: CommandAction
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Risk assessment model
# ---------------------------------------------------------------------------


class RiskAssessment(BaseModel):
    level: RiskLevel
    reason: str
    blocked_reason: str | None = None
    requires_confirmation: bool = False

    @property
    def is_blocked(self) -> bool:
        return self.level == RiskLevel.BLOCKED

    @property
    def can_proceed(self) -> bool:
        return self.level != RiskLevel.BLOCKED


# ---------------------------------------------------------------------------
# Grant model
# ---------------------------------------------------------------------------


class Grant(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["tx"] = "tx"
    band_start_hz: int
    band_stop_hz: int
    max_gain_db: int
    granted_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    revoked_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        return _utcnow() < self.expires_at

    @property
    def band_hz(self) -> tuple[int, int]:
        return (self.band_start_hz, self.band_stop_hz)

    def covers_frequency(self, freq_hz: int) -> bool:
        """True iff freq_hz is inside this grant's band (inclusive)."""
        return self.band_start_hz <= freq_hz <= self.band_stop_hz

    def covers_transmission(self, freq_hz: int, tx_vga_gain_db: int) -> bool:
        """True iff this grant permits a TX at (freq, gain).

        Requires BOTH: the frequency is in-band AND the requested gain is
        at or below the grant's max_gain_db. Grant must also be active.
        """
        if not self.is_active:
            return False
        if not self.covers_frequency(freq_hz):
            return False
        return tx_vga_gain_db <= self.max_gain_db


# ---------------------------------------------------------------------------
# Device info (plain dataclass — not user-supplied)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceInfo:
    serial: str
    firmware_version: str
    board_revision: str
    part_id: str


# ---------------------------------------------------------------------------
# Audit event model
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    trace_id: UUID
    session_id: str
    timestamp: float  # Unix epoch seconds, UTC
    event: AuditEventType
    action: CommandAction | None = None
    risk_level: RiskLevel | None = None
    payload_json: str | None = None  # already-serialized JSON string
    blocked_reason: str | None = None
    duration_ms: int | None = None
