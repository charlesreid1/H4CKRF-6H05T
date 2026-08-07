# spectrum-map-flag — the shape of a spectrogram IS the flag

ASCII text drawn as occupied vs unoccupied bins on a waterfall. Or a
QR code where black pixels are transmit-bursts and white pixels are
silences. Or a picture of the flag in the spectrogram itself.

## Signature

- **Broad occupied region:** many kHz to MHz wide, with structure that
  isn't a valid modulation shape.
- **Static structure:** the pattern doesn't move with time (unlike a
  real modulated signal).
- **Discrete grid:** individual bright pixels rather than continuous
  spectral lobes.

## Decode workflow

1. `capture_iq({freq: ..., duration: 10-60, sample_rate: 2000000+})`.
   Longer captures yield taller waterfalls (more time rows).
2. Compute a spectrogram — `scipy.signal.spectrogram(iq, fs=fs,
   nperseg=1024)`.
3. Threshold — the bright / dim binary image *is* the message.
4. Save as PNG and open in an image viewer. Some flags are literally
   the ASCII "flag{...}" drawn in the spectrogram.

## Common patterns

- **ASCII text horizontally:** 8-pixel-tall bright/dim rows encode a
  bit stream. Each 8-bit column is one character.
- **QR code:** a square block of bright/dim pixels; read with any QR
  scanner from the exported PNG.
- **Barcode:** vertical bright bars of varying width; read with a
  standard barcode library.
- **Morse in time:** a single narrow-band tone that keys on and off in
  Morse code.
- **Multi-tone chord:** a chord of tones whose frequencies encode a
  chord progression → interpret as ASCII (frequency mapped to bytes).

## Numpy sketch

```python
import numpy as np
from scipy.signal import spectrogram
from PIL import Image

f, t, Sxx = spectrogram(iq, fs=fs, nperseg=1024, noverlap=768, return_onesided=False)
Sxx_db = 10 * np.log10(np.abs(Sxx) + 1e-12)
Sxx_db = np.fft.fftshift(Sxx_db, axes=0)  # negative freqs on bottom

# threshold to bright/dim
img = ((Sxx_db - Sxx_db.min()) / (Sxx_db.max() - Sxx_db.min()) * 255).astype(np.uint8)
Image.fromarray(img).save("spectrogram.png")
```

Open `spectrogram.png` — the flag might be readable directly. If not,
try rotating 90° (some CTF authors draw vertically).

## Cross-references

- `../iq-analysis/reference.md` — spectrogram basics
- `../dsp/reference.md` — FFT sizing and PSD
- `waterfall-stego.md` — the sibling puzzle where the whole waterfall
  is the medium
