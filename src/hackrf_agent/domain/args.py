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
# analyze_iq_modulation
# ---------------------------------------------------------------------------


class AnalyzeIqModulationArgs(BaseModel):
    """Moment-based modulation classifier on a captured IQ file."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(
        default=2_000_000, description="Sample rate the file was captured at", gt=0
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# analyze_iq_symbols
# ---------------------------------------------------------------------------


class AnalyzeIqSymbolsArgs(BaseModel):
    """Estimate symbol rate from a captured IQ file via autocorrelation."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    min_rate_hz: float = Field(
        default=100.0, description="Lower bound for symbol-rate search (Hz)", gt=0
    )
    max_rate_hz: float | None = Field(
        default=None,
        description="Upper bound for symbol-rate search (Hz). Defaults to sample_rate_hz/8.",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# analyze_iq_spectrogram
# ---------------------------------------------------------------------------


class AnalyzeIqSpectrogramArgs(BaseModel):
    """Compact per-slice spectrogram summary (peak freq + power)."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    fft_size: int = Field(default=1024, description="FFT bins per slice", ge=64, le=65536)
    overlap: float = Field(default=0.5, description="Overlap fraction", ge=0.0, lt=0.95)
    max_slices: int = Field(default=512, description="Cap on returned slices", ge=1, le=8192)

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_manchester
# ---------------------------------------------------------------------------


class DecodeManchesterArgs(BaseModel):
    """Manchester line-code decoder over an OOK envelope."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    symbol_rate_hz: float = Field(..., description="Bit rate in Hz", gt=0)
    polarity: str = Field(
        default="ieee",
        description="Manchester polarity: 'ieee' (802.3, 01->1) or 'thomas' (G.E., 01->0).",
        pattern="^(ieee|thomas)$",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_pwm
# ---------------------------------------------------------------------------


class DecodePwmArgs(BaseModel):
    """Pulse-width-modulation decoder over an OOK envelope."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    short_us: float = Field(..., description="Nominal '0' pulse width in microseconds", gt=0)
    long_us: float = Field(..., description="Nominal '1' pulse width in microseconds", gt=0)

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _short_less_than_long(self) -> "DecodePwmArgs":
        if self.short_us >= self.long_us:
            raise ValueError(
                f"short_us ({self.short_us}) must be < long_us ({self.long_us})"
            )
        return self

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_ppm
# ---------------------------------------------------------------------------


class DecodePpmArgs(BaseModel):
    """Pulse-position-modulation decoder over an OOK envelope."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    pulse_us: float = Field(
        ..., description="Nominal pulse width in microseconds; symbol period is 2*pulse_us", gt=0
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_nrz / decode_nrzi
# ---------------------------------------------------------------------------


class DecodeNrzArgs(BaseModel):
    """NRZ / NRZI line-code decoder."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    symbol_rate_hz: float = Field(..., description="Bit rate in Hz", gt=0)
    variant: str = Field(
        default="nrz",
        description="'nrz' (level = bit) or 'nrzi' (transition = 1)",
        pattern="^(nrz|nrzi)$",
    )
    inverted: bool = Field(
        default=False, description="Invert polarity (NRZ only)."
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_pocsag
# ---------------------------------------------------------------------------


class DecodePocsagArgs(BaseModel):
    """POCSAG paging decoder (512 / 1200 / 2400 baud)."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    baud: int = Field(default=1200, description="POCSAG baud rate")

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _valid_baud(self) -> "DecodePocsagArgs":
        if self.baud not in (512, 1200, 2400):
            raise ValueError(f"baud must be 512, 1200, or 2400; got {self.baud}")
        return self

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_ads_b
# ---------------------------------------------------------------------------


class DecodeAdsBArgs(BaseModel):
    """Mode S / ADS-B decoder over captured 1090 MHz IQ."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(
        default=2_000_000,
        description="Capture rate. Must be >= 2 MHz for 0.5 μs chip resolution.",
        ge=2_000_000,
    )
    max_frames: int = Field(
        default=64,
        description="Maximum frames to decode from the capture.",
        ge=1,
        le=4096,
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_rtty
# ---------------------------------------------------------------------------


class DecodeRttyArgs(BaseModel):
    """RTTY / Baudot ITA2 decoder over a 2FSK envelope."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    baud: float = Field(
        default=45.45,
        description="RTTY baud rate. 45.45 (amateur), 50, 75, or 100.",
        gt=0,
    )
    invert: bool = Field(
        default=False,
        description="Swap MARK/SPACE polarity if the decoded text is nonsense.",
    )

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_ax25
# ---------------------------------------------------------------------------


class DecodeAx25Args(BaseModel):
    """AX.25 HDLC packet decoder (Bell 202 AFSK-1200 or direct FSK-9600)."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    baud: float = Field(default=1200.0, description="AX.25 baud rate (1200 or 9600 typical).", gt=0)
    invert: bool = Field(default=False, description="Swap FSK polarity if flag pattern is present but CRCs fail.")

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# decode_aprs
# ---------------------------------------------------------------------------


class DecodeAprsArgs(BaseModel):
    """APRS decoder — AX.25 UI frames with APRS payload interpretation."""

    iq_path: str = Field(..., description="Path to .iq file (must be under session root)")
    sample_rate_hz: int = Field(default=2_000_000, gt=0)
    baud: float = Field(default=1200.0, gt=0)
    invert: bool = Field(default=False)

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def iq_path_resolved(self) -> Path:
        return Path(self.iq_path)


# ---------------------------------------------------------------------------
# knowledge_list_topics
# ---------------------------------------------------------------------------


class KnowledgeListTopicsArgs(BaseModel):
    """No arguments — enumerate every topic dir under knowledge/."""

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# knowledge_read
# ---------------------------------------------------------------------------


class KnowledgeReadArgs(BaseModel):
    """Return the contents of one markdown file under knowledge/<topic>/."""

    topic: str = Field(
        ...,
        description="Topic directory name (e.g. 'dsp', 'ism-433'). Must match [a-z0-9][a-z0-9-]*.",
        min_length=1,
        max_length=64,
    )
    name: str = Field(
        ...,
        description="Markdown filename inside the topic dir (e.g. 'README.md', 'reference.md').",
        min_length=1,
        max_length=128,
    )

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# knowledge_search
# ---------------------------------------------------------------------------


class KnowledgeSearchArgs(BaseModel):
    """Case-insensitive substring search across every corpus markdown file."""

    query: str = Field(..., description="Substring to search for (case-insensitive).", min_length=1, max_length=200)
    max_results: int = Field(
        default=20,
        description="Maximum number of hits to return (1-200).",
        ge=1,
        le=200,
    )

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# knowledge_lookup_band
# ---------------------------------------------------------------------------


class KnowledgeLookupBandArgs(BaseModel):
    """Given a frequency in Hz, return the bands.json record(s) covering it."""

    freq_hz: int = Field(
        ...,
        description="Frequency of interest in Hz.",
        gt=0,
        le=6_000_000_000,
    )

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# knowledge_lookup_modulation
# ---------------------------------------------------------------------------


class KnowledgeLookupModulationArgs(BaseModel):
    """Given a modulation name/alias, return the modulations.json record."""

    name: str = Field(
        ...,
        description="Modulation family name or alias (e.g. 'OOK', 'GFSK', '2FSK', 'LoRa').",
        min_length=1,
        max_length=64,
    )

    model_config = {"frozen": True, "extra": "forbid"}


# ---------------------------------------------------------------------------
# knowledge_verify_claim
# ---------------------------------------------------------------------------


class KnowledgeVerifyClaimArgs(BaseModel):
    """Grade a factual claim against the trap catalog."""

    text: str = Field(
        ...,
        description="The claim to verify, as free text.",
        min_length=1,
        max_length=1000,
    )

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
    | AnalyzeIqModulationArgs
    | AnalyzeIqSymbolsArgs
    | AnalyzeIqSpectrogramArgs
    | DecodeManchesterArgs
    | DecodePwmArgs
    | DecodePpmArgs
    | DecodeNrzArgs
    | DecodePocsagArgs
    | DecodeAdsBArgs
    | DecodeRttyArgs
    | DecodeAx25Args
    | DecodeAprsArgs
    | KnowledgeListTopicsArgs
    | KnowledgeReadArgs
    | KnowledgeSearchArgs
    | KnowledgeLookupBandArgs
    | KnowledgeLookupModulationArgs
    | KnowledgeVerifyClaimArgs
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
    "analyze_iq_modulation": AnalyzeIqModulationArgs,
    "analyze_iq_symbols": AnalyzeIqSymbolsArgs,
    "analyze_iq_spectrogram": AnalyzeIqSpectrogramArgs,
    "decode_manchester": DecodeManchesterArgs,
    "decode_pwm": DecodePwmArgs,
    "decode_ppm": DecodePpmArgs,
    "decode_nrz": DecodeNrzArgs,
    "decode_pocsag": DecodePocsagArgs,
    "decode_ads_b": DecodeAdsBArgs,
    "decode_rtty": DecodeRttyArgs,
    "decode_ax25": DecodeAx25Args,
    "decode_aprs": DecodeAprsArgs,
    "knowledge_list_topics": KnowledgeListTopicsArgs,
    "knowledge_read": KnowledgeReadArgs,
    "knowledge_search": KnowledgeSearchArgs,
    "knowledge_lookup_band": KnowledgeLookupBandArgs,
    "knowledge_lookup_modulation": KnowledgeLookupModulationArgs,
    "knowledge_verify_claim": KnowledgeVerifyClaimArgs,
}
