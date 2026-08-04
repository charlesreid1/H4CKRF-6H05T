"""Generate tests/fixtures/iq/two_tone.iq — two CW tones at +/-150 kHz.

Reproducible from source — no HackRF needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def generate(out_path: str = "tests/fixtures/iq/two_tone.iq") -> None:
    sample_rate = 2_000_000
    num_samples = 50_000
    t = np.arange(num_samples, dtype=np.float32) / sample_rate
    tone_a = np.exp(2j * np.pi * 150_000.0 * t).astype(np.complex64)
    tone_b = np.exp(2j * np.pi * -150_000.0 * t).astype(np.complex64)
    iq = (tone_a + tone_b) * 0.5
    # Scale to int8 range with headroom.
    scaled = (iq * 100.0).astype(np.complex64)
    interleaved = np.empty(num_samples * 2, dtype=np.int8)
    interleaved[0::2] = scaled.real.astype(np.int8)
    interleaved[1::2] = scaled.imag.astype(np.int8)
    Path(out_path).write_bytes(interleaved.tobytes())


if __name__ == "__main__":
    generate()
