#!/usr/bin/env python3
"""Synthesize a HackRF-format IQ file containing a single complex tone.

Handy when kicking the tires on TX paths (chat CLI, MCP server, or bare
`hackrf_transfer`) without capturing a real signal first. The tone is
offset from the tuned center frequency by --offset-hz, so on-air you'll
see it at (center + offset).

HackRF's on-wire IQ format is interleaved signed int8, I then Q, at the
device's sample rate. This script writes exactly that.

Example:
    scripts/generate_tone_iq.py --out /tmp/tone_100k.iq
    hackrf-agent  # then: transmit /tmp/tone_100k.iq at 433.92 MHz, 10 dB, 1 s
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def synth_tone(
    sample_rate_hz: int,
    duration_s: float,
    offset_hz: float,
    amplitude: float,
) -> np.ndarray:
    """Return interleaved int8 I/Q samples for a complex exponential."""
    n = int(round(sample_rate_hz * duration_s))
    t = np.arange(n, dtype=np.float64) / sample_rate_hz
    sig = amplitude * np.exp(2j * np.pi * offset_hz * t)

    iq = np.empty(n * 2, dtype=np.int8)
    iq[0::2] = np.clip(sig.real * 127, -128, 127).astype(np.int8)
    iq[1::2] = np.clip(sig.imag * 127, -128, 127).astype(np.int8)
    return iq


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path("/tmp/tone.iq"),
                   help="Output path (default: /tmp/tone.iq)")
    p.add_argument("--sample-rate", type=int, default=8_000_000,
                   help="Sample rate in Hz (default: 8_000_000)")
    p.add_argument("--duration", type=float, default=1.0,
                   help="Duration in seconds (default: 1.0)")
    p.add_argument("--offset-hz", type=float, default=100_000,
                   help="Tone offset from tuned center in Hz (default: 100_000)")
    p.add_argument("--amplitude", type=float, default=0.3,
                   help="Amplitude in [0, 1]; keep < 1 to avoid clipping "
                        "(default: 0.3)")
    args = p.parse_args()

    if not 0 < args.amplitude <= 1:
        p.error("--amplitude must be in (0, 1]")

    iq = synth_tone(args.sample_rate, args.duration, args.offset_hz,
                    args.amplitude)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    iq.tofile(args.out)

    bytes_written = iq.nbytes
    print(f"wrote {bytes_written:,} bytes ({iq.size // 2:,} samples) "
          f"to {args.out}")
    print(f"  sample_rate = {args.sample_rate:,} Hz")
    print(f"  duration    = {args.duration} s")
    print(f"  tone offset = {args.offset_hz:+,.0f} Hz from center")
    print(f"  amplitude   = {args.amplitude}")


if __name__ == "__main__":
    main()
