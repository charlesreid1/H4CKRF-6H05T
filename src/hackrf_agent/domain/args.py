"""Typed argument models — one Pydantic model per ``CommandAction``.

Each model is the single source of truth for argument validation, defaults,
and JSON Schema generation. The CLI, the chat prompt, and the MCP tool
registry all derive their schemas from these models.

Every model is ``frozen=True`` because handlers read args, never mutate them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# get_device_info
# ---------------------------------------------------------------------------


class GetDeviceInfoArgs(BaseModel):
    """No arguments — read the attached HackRF's identity."""

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# sweep_spectrum
# ---------------------------------------------------------------------------


class SweepSpectrumArgs(BaseModel):
    """RX-only sweep over a band; returns top-N peaks and noise floor."""

    start_freq_hz: int = Field(..., description="Start of sweep band in Hz", gt=0)
    end_freq_hz: int = Field(..., description="End of sweep band in Hz", gt=0)
    sample_rate_hz: int = Field(
        default=2_000_000, description="Sample rate in Hz", gt=0
    )
    lna_gain_db: int = Field(default=16, description="LNA gain in dB (0-40)")
    vga_gain_db: int = Field(default=20, description="VGA gain in dB (0-62)")
    rf_amp_db: int = Field(default=0, description="RF amp gain in dB (0-14)")
    dwell_s: float = Field(default=1.0, description="Dwell time per hop in seconds", gt=0)
    fft_size: int = Field(default=4096, description="FFT bin count", gt=0)

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# capture_iq
# ---------------------------------------------------------------------------


class CaptureIqArgs(BaseModel):
    """RX capture into an .iq file under the session directory."""

    center_freq_hz: int | None = Field(
        default=None, description="Center frequency in Hz (explicit tuning)",
    )
    target_freq_hz: int | None = Field(
        default=None,
        description=(
            "Frequency of interest in Hz. If set, the tuner picks a center "
            "offset by ~sample_rate/4 so the DC/LO spike does not land on "
            "target_freq_hz. Exactly one of center_freq_hz or target_freq_hz "
            "must be given."
        ),
        gt=0,
    )
    sample_rate_hz: int = Field(
        default=2_000_000, description="Sample rate in Hz", gt=0
    )
    duration_s: float = Field(..., description="Capture duration in seconds", gt=0)
    lna_gain_db: int = Field(default=16, description="LNA gain in dB (0-40)")
    vga_gain_db: int = Field(default=20, description="VGA gain in dB (0-62)")
    rf_amp_db: int = Field(default=0, description="RF amp gain in dB (0-14)")

    @model_validator(mode="after")
    def _one_of_center_or_target(self) -> "CaptureIqArgs":
        have_center = self.center_freq_hz is not None
        have_target = self.target_freq_hz is not None
        if have_center == have_target:
            raise ValueError(
                "provide exactly one of center_freq_hz or target_freq_hz"
            )
        if have_center and self.center_freq_hz is not None and self.center_freq_hz <= 0:
            raise ValueError("center_freq_hz must be > 0")
        return self

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# transmit_iq
# ---------------------------------------------------------------------------


class TransmitIqArgs(BaseModel):
    """TX from an existing .iq file. Requires an active grant."""

    center_freq_hz: int = Field(..., description="Center frequency in Hz", gt=0)
    sample_rate_hz: int = Field(
        default=2_000_000, description="Sample rate in Hz", gt=0
    )
    iq_path: str = Field(
        ..., description="Path to .iq file (must be under session root)"
    )
    tx_vga_gain_db: int = Field(..., description="TX VGA gain in dB (0-47)")
    rf_amp_db: int = Field(default=0, description="RF amp gain in dB (0-14)")

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# read_iq_summary
# ---------------------------------------------------------------------------


class ReadIqSummaryArgs(BaseModel):
    """Re-summarize a previously captured .iq file. No hardware access."""

    iq_path: str = Field(
        ..., description="Path to .iq file (must be under session root)"
    )
    center_freq_hz: int = Field(..., description="Center frequency in Hz", gt=0)
    sample_rate_hz: int = Field(
        default=2_000_000, description="Sample rate in Hz", gt=0
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_ook
# ---------------------------------------------------------------------------


class DecodeOokArgs(BaseModel):
    """Attempt OOK bit decoding of an .iq file (placeholder)."""

    iq_path: str = Field(
        ..., description="Path to .iq file (must be under session root)"
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# grant_list
# ---------------------------------------------------------------------------


class GrantListArgs(BaseModel):
    """No arguments — list currently active TX grants."""

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# audit_query
# ---------------------------------------------------------------------------


class AuditQueryArgs(BaseModel):
    """Query the audit log; returns recent rows."""

    session_id: str | None = Field(
        default=None, description="Optional session ID filter"
    )
    limit: int = Field(default=50, description="Max rows to return", gt=0, le=1000)

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# Discriminated union (for generating a single tool schema in the chat prompt)
# ---------------------------------------------------------------------------


ActionArgs = (
    GetDeviceInfoArgs
    | SweepSpectrumArgs
    | CaptureIqArgs
    | TransmitIqArgs
    | ReadIqSummaryArgs
    | DecodeOokArgs
    | GrantListArgs
    | AuditQueryArgs
)


# ---------------------------------------------------------------------------
# Lookup table — maps each CommandAction to its args model
# ---------------------------------------------------------------------------

ARGS_BY_ACTION: dict[str, type[BaseModel]] = {
    "get_device_info": GetDeviceInfoArgs,
    "sweep_spectrum": SweepSpectrumArgs,
    "capture_iq": CaptureIqArgs,
    "transmit_iq": TransmitIqArgs,
    "read_iq_summary": ReadIqSummaryArgs,
    "decode_ook": DecodeOokArgs,
    "grant_list": GrantListArgs,
    "audit_query": AuditQueryArgs,
}
