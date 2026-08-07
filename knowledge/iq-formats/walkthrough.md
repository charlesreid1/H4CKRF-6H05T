# iq-formats/walkthrough.md — conversions in numpy

## Load HackRF `.cs8` → complex64

```python
import numpy as np
raw = np.fromfile('capture.cs8', dtype=np.int8)
x = raw[::2].astype(np.float32) / 128 + 1j * raw[1::2].astype(np.float32) / 128
# x is complex64, values in [-1, +1] (approximately)
```

## Load RTL-SDR `.cu8` → complex64 (mind the bias)

```python
raw = np.fromfile('capture.cu8', dtype=np.uint8).astype(np.float32)
raw -= 127.5     # remove the ~127 bias
x = raw[::2] / 127.5 + 1j * raw[1::2] / 127.5
```

Skipping the bias step is one of the most common IQ-loading bugs; the
resulting file will have a huge DC offset even though the actual RF
had none.

## Load GNU Radio `.cf32` → complex64

```python
x = np.fromfile('capture.cf32', dtype=np.complex64)
```

`.cf32` is the "just works" format for numpy — no conversion needed.

## Convert complex64 → `.cs8` for `hackrf_transfer`

```python
# Scale to int8 range, clip to avoid wrap.
x_clip = np.clip(x, -0.999, +0.999)
interleaved = np.empty(2 * len(x_clip), dtype=np.int8)
interleaved[::2] = (x_clip.real * 127).astype(np.int8)
interleaved[1::2] = (x_clip.imag * 127).astype(np.int8)
interleaved.tofile('to_transmit.cs8')
```

Then `hackrf_transfer -t to_transmit.cs8 -f 433920000 -s 2000000` (from
outside this MCP — the MCP's `transmit_iq` verb is the gated path).

## Convert complex64 → WAV (SDR# / HDSDR compatible)

```python
from scipy.io import wavfile
# SDR# wants float32, stereo, with sample rate = capture sample rate.
stereo = np.column_stack((x.real.astype(np.float32),
                          x.imag.astype(np.float32)))
wavfile.write('capture.wav', fs, stereo)
```

WAV headers cap `fs` at whatever the WAV field can hold; for extreme
rates prefer `.cf32` or SigMF.

## Author a SigMF pair

```python
import json
x.astype(np.complex64).tofile('capture.sigmf-data')
meta = {
    "global": {
        "core:datatype": "cf32_le",
        "core:sample_rate": fs,
        "core:version": "1.0.0",
        "core:hw": "HackRF One",
    },
    "captures": [
        {"core:sample_start": 0, "core:frequency": 433920000}
    ],
    "annotations": []
}
with open('capture.sigmf-meta', 'w') as f:
    json.dump(meta, f, indent=2)
```

## Guess a file's format from its size

Given a capture at `fs = 10 MHz` for `duration = 2 s`, expected
samples is `20 000 000`. The file size lets you back out
`bytes_per_sample`:

- `40 MB` → 2 bytes/sample → `.cs8` or `.cu8` (8-bit interleaved)
- `80 MB` → 4 bytes/sample → `.cs16`
- `160 MB` → 8 bytes/sample → `.cf32`

If sample rate or duration is unknown, this trick doesn't work; try
loading with each dtype and inspect the spectrum shape — the wrong
dtype produces obvious artifacts.
