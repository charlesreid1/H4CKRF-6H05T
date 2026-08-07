# `ism_315_noise_only.iq` — provenance

- **Source:** Synthesised by `tests/fixtures/iq/generate_ism_315_noise_only.py` (deterministic).
- **Center frequency:** 315 MHz (nominal).
- **Sample rate:** 2 Msps.
- **Signal:** Noise floor only — normally-distributed int8 samples.
- **Duration:** 50,000 samples (25 ms).
- **Gain settings:** N/A (synthetic).
- **Recording date:** N/A — synthetic (deterministic).
- **Machine:** Any; no HackRF required.
- **Capture recipe (real hardware):**
  ```
  hackrf_transfer -r /tmp/quiet.iq -f 315000000 -s 2000000 -l 16 -g 20 -n 100000
  head -c 100000 /tmp/quiet.iq > tests/fixtures/iq/ism_315_noise_only.iq
  ```
- **What a passing test asserts:** FFT peak prominence is under 6 dB (no signal present).
