"""Pure string parsers for CLI band, duration, and gain arguments.

Zero I/O. Imports only stdlib + :mod:`hackrf_agent.domain.frequency_policy`.
"""

from __future__ import annotations

import re
from typing import Final

from hackrf_agent.domain.frequency_policy import ISM_BANDS

# unit multiplier in Hz
_UNIT_MULT: Final[dict[str, int]] = {
    "": 1,
    "k": 1_000,
    "K": 1_000,
    "M": 1_000_000,
    "G": 1_000_000_000,
}

_BAND_RANGE_RE: Final = re.compile(
    r"^\s*(?P<a>\d+(?:\.\d+)?)(?P<au>[kKMG]?)\s*-\s*"
    r"(?P<b>\d+(?:\.\d+)?)(?P<bu>[kKMG]?)\s*$"
)

_BAND_SINGLE_RE: Final = re.compile(
    r"^\s*(?P<a>\d+(?:\.\d+)?)(?P<au>[kKMG]?)\s*$"
)


def parse_band(spec: str) -> tuple[int, int]:
    """Parse a band spec string into (start_hz, stop_hz).

    Supported forms:
      "433.05-434.79M"  →  (433_050_000, 434_790_000)
      "902M-928M"       →  (902_000_000, 928_000_000)
      "902M-928000000"  →  (902_000_000, 928_000_000)  # mixed units OK
      "315M"            →  the named ISM band containing 315 MHz — i.e.
                           (310_000_000, 320_000_000) from ISM_BANDS.
      "1000000-2000000" →  (1_000_000, 2_000_000)  # raw Hz

    Raises ValueError on malformed input, unknown units, start >= stop,
    or a single-value form that does not fall inside any known ISM band.
    """
    m = _BAND_RANGE_RE.match(spec)
    if m:
        au = m.group("au")
        bu = m.group("bu")
        a_val = m.group("a")
        b_val = m.group("b")
        # If one side lacks a unit, inherit from the other side when the
        # bare number is clearly not a raw-Hz value: it's fractional or too
        # small to be a sensible SDR frequency in Hz.
        # "433.05-434.79M" → M applies to both (fractional).
        # "500-400M" → M applies to both (500 Hz is not a sensible band).
        # "902M-928000000" → 928000000 is large → raw Hz (mixed units OK).
        if (not au and bu
                and ("." in a_val or int(float(a_val)) < 1_000_000)):
            au = bu
        elif (not bu and au
              and ("." in b_val or int(float(b_val)) < 1_000_000)):
            bu = au
        start = _to_hz(a_val, au)
        stop = _to_hz(b_val, bu)
        if start >= stop:
            raise ValueError(f"band start {start} must be < stop {stop}")
        return start, stop

    m = _BAND_SINGLE_RE.match(spec)
    if m:
        center_hz = _to_hz(m.group("a"), m.group("au"))
        for band_start, band_stop, _label in ISM_BANDS:
            if band_start <= center_hz <= band_stop:
                return band_start, band_stop
        raise ValueError(
            f"single-value band {spec!r} ({center_hz} Hz) is not inside "
            f"any known ISM band; use an explicit range like '433.05-434.79M'"
        )

    raise ValueError(f"unparseable band {spec!r}")


def _to_hz(number_str: str, unit: str) -> int:
    mult = _UNIT_MULT.get(unit)
    if mult is None:  # unreachable — regex constrains unit
        raise ValueError(f"unknown unit {unit!r}")
    value = float(number_str) * mult
    if value <= 0 or value != int(value) and mult == 1:
        # Fractional raw-Hz is nonsense; fractional M/G is fine.
        raise ValueError(f"non-integer Hz value from {number_str}{unit}")
    return int(value)


# ---------------------------------------------------------------------------
# duration
# ---------------------------------------------------------------------------

_DURATION_RE: Final = re.compile(r"^\s*(?P<n>\d+)\s*(?P<u>[smh])\s*$")

_DURATION_MULT: Final[dict[str, int]] = {"s": 1, "m": 60, "h": 3600}


def parse_duration(spec: str) -> int:
    """Parse a duration string into seconds.

    Supported forms:  "90s", "30m", "2h".  No mixed forms — "1h30m" is
    a ValueError.  No day/week suffixes.
    """
    m = _DURATION_RE.match(spec)
    if not m:
        raise ValueError(f"unparseable duration {spec!r}")
    n = int(m.group("n"))
    if n <= 0:
        raise ValueError(f"duration must be > 0, got {n}")
    return n * _DURATION_MULT[m.group("u")]


# ---------------------------------------------------------------------------
# gain
# ---------------------------------------------------------------------------


def parse_gain_db(value: int) -> int:
    """Validate that gain is in [0, 62] dB and return it.

    The CLI accepts an int; we validate here so the error message is
    CLI-flavored, not driver-flavored.
    """
    if value < 0 or value > 62:
        raise ValueError(
            f"gain must be in [0, 62] dB, got {value}. "
            "See docs/safety.md for the discrete gain grids."
        )
    return value
