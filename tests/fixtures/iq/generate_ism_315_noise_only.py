"""Generate tests/fixtures/iq/ism_315_noise_only.iq — synthetic placeholder.

Simulates noise floor at 315 MHz center. Replace with a real capture
from a quiet indoor environment when HackRF hardware is available.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def generate(out_path: str = "tests/fixtures/iq/ism_315_noise_only.iq") -> None:
    num_samples = 50_000
    # Higher-amplitude noise so random peaks don't exceed prominence threshold.
    noise = (np.random.default_rng(42).normal(0, 20, num_samples * 2)).astype(np.int8)
    Path(out_path).write_bytes(noise.tobytes())


if __name__ == "__main__":
    generate()
