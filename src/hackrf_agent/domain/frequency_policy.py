"""Frequency band tables and lookup functions.

Pure data + lookup helpers. Zero I/O.

Every blocked band listed here MUST have a corresponding entry in
``docs/safety.md`` — this module is a *transcription*, not a source of
new policy.
"""

# ---------------------------------------------------------------------------
# Blocked bands — absolute TX prohibitions
#
# Format: (start_hz, stop_hz, reason)   — both edges inclusive.
#
# Intentional overlaps (documented):
#   - VHF Guard (121.4–121.6) is nested inside Aviation Voice (118–137)
#   - LTE Band 17 (734–746) is nested inside LTE Band 12 (729–746)
# Both bands are BLOCKED regardless, so overlapping checks are harmless.
# ---------------------------------------------------------------------------

BLOCKED_BANDS: list[tuple[int, int, str]] = [
    # Aviation safety-of-life
    (1_087_000_000, 1_093_000_000, "ADS-B/SSR/TCAS — 47 CFR §87.131"),
    (118_000_000, 137_000_000, "Aviation voice communications — 47 CFR §87.171"),
    (
        121_400_000,
        121_600_000,
        "International aeronautical emergency — ICAO Annex 10",
    ),
    # GNSS / satellite navigation
    (1_559_000_000, 1_591_000_000, "GPS L1 — ITU RR RNSS allocation"),
    (1_215_000_000, 1_240_000_000, "GPS L2 — ITU RR RNSS allocation"),
    (1_164_000_000, 1_189_000_000, "GPS L5 safety-of-life — ITU RR"),
    (1_592_952_500, 1_610_485_000, "GLONASS G1 — ITU RR"),
    (1_237_827_500, 1_254_427_500, "GLONASS G2 — ITU RR"),
    (1_260_000_000, 1_300_000_000, "Galileo E6 — ITU RR"),
    # Maritime distress / safety
    (156_762_500, 156_837_500, "Maritime distress/safety — 47 CFR §80.369"),
    # Cellular downlink bands (US)
    (729_000_000, 746_000_000, "Cellular downlink Band 12 — 47 CFR Part 27"),
    (746_000_000, 756_000_000, "Cellular downlink Band 13 — 47 CFR Part 27"),
    (734_000_000, 746_000_000, "Cellular downlink Band 17 — 47 CFR Part 27"),
    (869_000_000, 894_000_000, "Cellular downlink Band 5 — 47 CFR Part 22H"),
    (1_930_000_000, 1_990_000_000, "Cellular downlink Band 2 — 47 CFR Part 24E"),
    (2_110_000_000, 2_155_000_000, "Cellular downlink Band 4 — 47 CFR Part 27"),
    # Emergency services
    (758_000_000, 775_000_000, "Public safety narrowband/broadband — FirstNet"),
    (851_000_000, 854_000_000, "Public safety NPSPAC — 47 CFR Part 90"),
    # Radio astronomy & passive services
    (1_400_000_000, 1_427_000_000, "Radio astronomy 21 cm — ITU-R RA.769"),
    (406_100_000, 410_000_000, "Radio astronomy protected — ITU-R RA.769"),
    (608_000_000, 614_000_000, "Radio astronomy protected — ITU-R RA.769"),
    (2_690_000_000, 2_700_000_000, "Radio astronomy protected — ITU-R RA.769"),
]

# ---------------------------------------------------------------------------
# ISM bands — unlicensed operation under FCC Part 15
#
# Format: (start_hz, stop_hz, label)
# ---------------------------------------------------------------------------

ISM_BANDS: list[tuple[int, int, str]] = [
    (310_000_000, 320_000_000, "ISM 315 MHz — 47 CFR §15.231"),
    (
        433_050_000,
        434_790_000,
        "ISM 433.05–434.79 MHz — ETSI EN 300 220 (Region 1)",
    ),
    (902_000_000, 928_000_000, "ISM 902–928 MHz — 47 CFR §15.247/§15.249"),
    (
        2_400_000_000,
        2_483_500_000,
        "ISM 2400–2483.5 MHz — 47 CFR §15.247/§15.249",
    ),
    (
        5_725_000_000,
        5_875_000_000,
        "ISM 5725–5875 MHz — 47 CFR §15.247/§15.249",
    ),
]

# ---------------------------------------------------------------------------
# Amateur radio bands — reference-only
#
# Used by the risk assessor to classify TX in amateur bands as HIGH
# (licensed-operator territory). Not used for blocking.
#
# Format: (start_hz, stop_hz, label)
#
# When a frequency falls in BOTH an ISM band and an amateur band,
# ISM classification wins. Callers must check is_in_ism() first.
# ---------------------------------------------------------------------------

AMATEUR_BANDS: list[tuple[int, int, str]] = [
    (222_000_000, 225_000_000, "1.25 m amateur — 47 CFR Part 97"),
    (420_000_000, 450_000_000, "70 cm amateur — 47 CFR Part 97"),
    (902_000_000, 928_000_000, "33 cm amateur (secondary to ISM)"),
    (1_240_000_000, 1_300_000_000, "23 cm amateur — 47 CFR Part 97"),
    (2_390_000_000, 2_450_000_000, "13 cm amateur — 47 CFR Part 97"),
]

# ---------------------------------------------------------------------------
# Subprocess allowlists (referenced by Part 4 executor)
# ---------------------------------------------------------------------------

SAFE_HACKRF_PREFIXES: list[str] = [
    "hackrf_info",
    "hackrf_spiflash -r",
    "hackrf_sweep -1",  # one-shot RX sweep, bounded
]

MEDIUM_HACKRF_PREFIXES: list[str] = [
    "hackrf_transfer -r",  # RX-only capture
]
# Anything else → HIGH.  Any `-t` flag in argv → HIGH regardless of prefix.


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------


def is_blocked(freq_hz: int) -> tuple[bool, str | None]:
    """Check whether a frequency falls in any BLOCKED_BAND.

    Returns (True, reason) if blocked, else (False, None).
    Range check is inclusive on both edges.
    """
    for start_hz, stop_hz, reason in BLOCKED_BANDS:
        if start_hz <= freq_hz <= stop_hz:
            return (True, reason)
    return (False, None)


def is_in_ism(freq_hz: int) -> tuple[bool, str | None]:
    """Check whether a frequency falls in any ISM_BAND.

    Returns (True, label) if in ISM, else (False, None).
    """
    for start_hz, stop_hz, label in ISM_BANDS:
        if start_hz <= freq_hz <= stop_hz:
            return (True, label)
    return (False, None)


def is_in_amateur(freq_hz: int) -> tuple[bool, str | None]:
    """Check whether a frequency falls in any AMATEUR_BAND.

    Returns (True, label) if in an amateur band, else (False, None).
    Callers should check `is_in_ism` first — ISM classification wins on overlap.
    """
    for start_hz, stop_hz, label in AMATEUR_BANDS:
        if start_hz <= freq_hz <= stop_hz:
            return (True, label)
    return (False, None)


def range_is_blocked(start_hz: int, stop_hz: int) -> tuple[bool, str | None]:
    """Check whether a sweep range overlaps ANY blocked band.

    Used by SWEEP_SPECTRUM: even a receive-only sweep across a blocked band
    is not itself illegal, but we still surface the overlap so the assessor
    can decide what to do.

    Returns (True, reason) on first overlap, else (False, None).
    Overlap definition: two ranges overlap iff
    ``a.start <= b.stop AND b.start <= a.stop``.
    """
    for b_start, b_stop, reason in BLOCKED_BANDS:
        if start_hz <= b_stop and b_start <= stop_hz:
            return (True, reason)
    return (False, None)
