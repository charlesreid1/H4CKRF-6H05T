# fsk-gfsk-msk-gmsk/walkthrough.md — pipelines

## 2FSK: POCSAG-style capture → bits

```python
import numpy as np

fs = 2_000_000
raw = np.fromfile("pocsag.cs8", dtype=np.int8)
iq = (raw[::2] + 1j * raw[1::2]).astype(np.complex64) / 128.0

# 1. Instantaneous frequency
phase = np.unwrap(np.angle(iq))
inst_f = np.diff(phase) * fs / (2 * np.pi)

# 2. Coarse frequency offset removal
inst_f -= np.mean(inst_f)

# 3. Downsample to symbol rate (POCSAG 1200 baud)
symbol_rate = 1200
sps = int(fs / symbol_rate)
inst_f_ds = inst_f[::sps]

# 4. Slice around zero (mark = +Δf, space = -Δf)
bits = (inst_f_ds > 0).astype(np.uint8)

# 5. Hand off to multimon-ng or a POCSAG codeword decoder
```

Real POCSAG decoders also handle preamble detection (a 0xAAAA... sync
run), 32-bit codeword alignment, BCH(31,21) error correction, and the
address/message extraction. `multimon-ng -a POCSAG1200` is the
canonical downstream tool.

## GFSK: BLE advertising channel (illustrative — HackRF struggles at 1 Mbaud)

```python
import numpy as np

fs = 4_000_000
symbol_rate = 1_000_000
sps = int(fs / symbol_rate)

# assume iq is a captured BLE advertising packet at chan 37 (2.402 GHz)
# quadrature demodulator (works for GFSK regardless of BT product)
y = iq[1:] * np.conj(iq[:-1])
inst_f = np.angle(y) * fs / (2 * np.pi)

# matched filter with a Gaussian pulse of BT=0.5
from scipy.signal import gaussian
h = gaussian(int(0.5 * sps), std=0.5 * sps / 3)
h /= h.sum()
inst_f_filt = np.convolve(inst_f, h, mode='same')

bits = (inst_f_filt[::sps] > 0).astype(np.uint8)
```

Caveat — BLE also uses whitening (a 7-bit LFSR XOR over the payload)
that must be reversed before parsing.

## GMSK: AIS frame

AIS is easier than BLE because it's slower (9.6 kbaud) and channelized:

```python
import numpy as np

fs = 240_000                     # after decimation
symbol_rate = 9_600
sps = int(fs / symbol_rate)

y = iq[1:] * np.conj(iq[:-1])
inst_f = np.angle(y)

# HDLC 0x7E flag detection (bit-stuffed after 5 ones)
bits = (inst_f[::sps] > 0).astype(np.uint8)
# ... find sync 0x7E7E, de-stuff, extract 24-bit AIVDM payload, CRC check
```

For anything past a toy prototype, `gr-ais` in GNU Radio has the full
NRZI + bit-stuff + CRC + AIVDM stack.

## 4FSK: DMR / P25 C4FM at 4800 sym/s

Four discrete frequency levels. Instead of a binary slicer, use a
4-level slicer:

```python
inst_f_ds = inst_f[::sps]
# four levels at ±3Δf and ±Δf; slice at ±2Δf and 0
symbols = np.digitize(inst_f_ds, bins=[-2*delta_f, 0, 2*delta_f])
# symbols ∈ {0, 1, 2, 3} = -3Δf, -Δf, +Δf, +3Δf
```

Hand off to `DSD+` or `SDRTrunk` for the full P25/DMR frame layer.
