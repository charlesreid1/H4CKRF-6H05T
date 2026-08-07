# psk-qam/walkthrough.md — pipelines

## BPSK toy demod (already near-baseband, near-symbol-rate)

```python
import numpy as np

fs = 4_000_000
symbol_rate = 927_000    # GOES HRIT
sps = int(fs / symbol_rate)

# assume iq is coarse-recovered (LO error <100 Hz) and near-symbol-rate
sym = iq[::sps]
bits = (sym.real > 0).astype(np.uint8)
```

This works when the capture is clean; for real signals you need:

1. **Frequency correction:** a squaring loop or Costas loop.
2. **Matched filter:** convolve with an RRC pulse.
3. **Symbol timing recovery:** Gardner (2 samples/symbol) driving an
   NCO.

GNU Radio's `symbol_sync` block bundles steps 2-3.

## QPSK — constellation classification

```python
import numpy as np

# assume iq is carrier-recovered, matched-filtered, symbol-sampled
sym = iq[::sps]

# quadrant classification (Gray-mapped: 00, 01, 11, 10)
def qpsk_slice(z):
    i = (z.real > 0).astype(np.uint8)
    q = (z.imag > 0).astype(np.uint8)
    return (i << 1) | q

bits2 = qpsk_slice(sym)
```

## 16-QAM — nearest-neighbor slice

```python
import numpy as np

# expected constellation (Gray-coded 4-bit indices)
levels = np.array([-3, -1, 1, 3])
i_points, q_points = np.meshgrid(levels, levels)
constellation = (i_points + 1j * q_points).ravel()

def qam16_slice(z, constellation):
    # nearest-neighbor by |z - c|
    d = np.abs(z[:, None] - constellation[None, :])
    idx = np.argmin(d, axis=1)
    return idx.astype(np.uint8)

sym = iq[::sps]
sym *= (3 / np.max(np.abs(sym)))       # normalize to constellation scale
labels = qam16_slice(sym, constellation)
```

The Gray-code map from `labels` → 4-bit values is a fixed lookup for
the chosen constellation labeling.

## DQPSK / π/4-DQPSK

The trick: use *phase differences* rather than absolute phase:

```python
# multiply each symbol by the conjugate of the previous
diff = sym[1:] * np.conj(sym[:-1])
# slice on the angle
angles = np.angle(diff)
```

For π/4-DQPSK (TETRA), rotate by π/4 between symbols before slicing to
avoid the constellation walking off through zero.

## What to reach for after numpy

Real receivers should not be built from numpy. Use:

- **GNU Radio** — `qa_symbol_sync`, `costas_loop`, `constellation_decoder`.
- **gr-osmosdr** — HackRF driver as source.
- **SDRAngel** — for common broadcast modes; DVB-S/DVB-T built in.
- **SigDigger** — GUI constellation viewer for triage.
