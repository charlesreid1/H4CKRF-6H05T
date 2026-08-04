# `two_tone.iq` — provenance

- **Source:** Synthesised by `tests/fixtures/iq/two_tone.py`.
- **Center frequency:** 433 MHz (nominal — the tones are at ±150 kHz offset).
- **Sample rate:** 2 Msps.
- **Duration:** 50,000 samples (25 ms).
- **Gain settings:** N/A (synthetic).
- **Recording date:** N/A — reproducible from the script.
- **Machine:** Any; no HackRF required.
- **What a passing test asserts:** FFT shows two peaks symmetric about center within one FFT bin of ±150 kHz.
