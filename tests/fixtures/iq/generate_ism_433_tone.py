"""Generate tests/fixtures/iq/ism_433_tone.iq — synthetic placeholder.

Simulates a CW tone at +200 kHz from center (433.92 MHz + 200 kHz = 434.12 MHz).
Replace with a real keyfob capture when HackRF hardware is available.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def generate(out_path: str = "tests/fixtures/iq/ism_433_tone.iq") -> None:
    sample_rate = 2_000_000
    tone_offset_hz = 200_000  # 200 kHz above 433.92 MHz center → 434.12 MHz
    num_samples = 50_000
    t = np.arange(num_samples, dtype=np.float32) / sample_rate
    # CW tone at the specified offset.
    iq = np.exp(2j * np.pi * tone_offset_hz * t).astype(np.complex64)
    # Scale to int8 range.
    scaled = (iq * 100.0).astype(np.complex64)
    interleaved = np.empty(num_samples * 2, dtype=np.int8)
    interleaved[0::2] = scaled.real.astype(np.int8)
    interleaved[1::2] = scaled.imag.astype(np.int8)
    Path(out_path).write_bytes(interleaved.tobytes())


if __name__ == "__main__":
    generate()
