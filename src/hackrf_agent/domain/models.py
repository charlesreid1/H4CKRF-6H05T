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
    ANALYZE_PULSES = "analyze_pulses"
    DEMODULATE_BITS = "demodulate_bits"
    GRANT_LIST = "grant_list"
    AUDIT_QUERY = "audit_query"

    @classmethod
    def _missing_(cls, value: object) -> "CommandAction | None":
        # Backward-compatible aliases.  ``decode_ook`` was the pre-0.6 name
        # for what is now ``analyze_pulses``; keep it accepted for one release
        # cycle so saved transcripts and plans don't break.
        if value == "decode_ook":
            return cls.ANALYZE_PULSES
        return None


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
