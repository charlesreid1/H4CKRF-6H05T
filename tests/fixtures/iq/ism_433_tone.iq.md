# `ism_433_tone.iq` — provenance

- **Source:** Synthesised by `tests/fixtures/iq/generate_ism_433_tone.py` (placeholder).
- **Center frequency:** 433.92 MHz.
- **Sample rate:** 2 Msps.
- **Signal:** One CW tone at +200 kHz offset (434.12 MHz).
- **Duration:** 50,000 samples (25 ms).
- **Gain settings:** N/A (synthetic).
- **Recording date:** N/A — synthetic placeholder.
- **Machine:** Any; no HackRF required.
- **Capture recipe (real hardware):**
  ```
  hackrf_transfer -r /tmp/keyfob.iq -f 433920000 -s 2000000 -l 16 -g 20 -n 100000
  head -c 100000 /tmp/keyfob.iq > tests/fixtures/iq/ism_433_tone.iq
  ```
- **What a passing test asserts:** FFT peak within one bin of 434.12 MHz (200 kHz above center at 433.92 MHz).
