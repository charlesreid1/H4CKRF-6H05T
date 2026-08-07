# frequency-hop-flag — the hop pattern encodes the flag

A pseudo-FHSS transmitter hops between N channels on a schedule. The
sequence of channel indices decodes to ASCII, hex, or binary.

## Signature

- **Waterfall:** short bursts at different frequencies, repeating.
- **Constant symbol rate per burst:** each hop is one modulated
  chunk, ~ms to tens of ms long.
- **Discrete channel set:** N (typically 8-32) distinct frequencies
  in use, not a continuous slide.
- **Pattern length:** the same sequence repeats after M hops (short
  enough to spot in a 10-30 s capture).

## Decode workflow

1. `sweep_spectrum({start, end, dwell_s=1})` to establish the channel
   set.
2. `capture_iq({freq, duration: 30, sample_rate: covers-all-channels,
   bandwidth: wide})`. If channels span >20 MHz, you may need multiple
   captures.
3. Detect each hop's center frequency — find bright peaks per time
   window in a spectrogram.
4. Convert peak positions into a sequence of channel indices.
5. Interpret the sequence:
   - **N=2, indices ∈ {0,1}:** binary bitstream → hex bytes → ASCII.
   - **N=16, indices ∈ 0..15:** hex nibbles → hex bytes → ASCII.
   - **N=32, indices ∈ 0..31:** 5-bit codes → maybe base32.
   - **N=64:** base64 alphabet.
   - **N=26 or 27:** letters A-Z (or A-Z + space) directly.

## Numpy sketch

```python
import numpy as np
from scipy.signal import spectrogram

f, t, Sxx = spectrogram(iq, fs=fs, nperseg=8192, noverlap=6144, return_onesided=False)

# per time slice, find the brightest bin
peaks = np.argmax(np.abs(Sxx), axis=0)
freqs_of_peaks = f[peaks]

# quantize to the discrete channel set (find unique clusters)
from sklearn.cluster import KMeans
labels = KMeans(n_clusters=N_CHANNELS).fit_predict(freqs_of_peaks.reshape(-1, 1))

# now labels is a sequence of channel indices
```

## Sanity checks

- **Regular hop timing** (each burst ~equal duration) → the schedule
  is deterministic. Good.
- **Irregular hop timing** → the timing might itself be information;
  measure inter-burst gap as an additional dimension.
- **Bursts with different modulation content per hop** → the *content*
  of each hop is a bit or nibble; hops themselves are just delivery
  frames.

## Cross-references

- `../modulation/dsss-fhss/reference.md` — real FHSS
- `../modulation/dsss-fhss/recognition.md` — waterfall triage
- `spectrum-map-flag.md` — the sibling "waterfall shape" puzzle
