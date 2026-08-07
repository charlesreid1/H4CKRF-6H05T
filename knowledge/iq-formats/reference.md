# iq-formats/reference.md — the file layer

Every capture becomes bytes on disk. The bytes always disagree with each
other about layout, sample type, endianness, or metadata. This is the
authoritative table.

## Formats

| Extension | Sample layout | Bits | Interleaving | Endianness | Header | Canonical source |
|-----------|---------------|------|--------------|------------|--------|------------------|
| `.iq` | ambiguous | any | usually IQIQIQ | usually LE | none | community |
| `.cs8` | int8, signed | 8 | I then Q, interleaved | LE | none | HackRF `hackrf_transfer` |
| `.cu8` | uint8, unsigned (biased ~127) | 8 | I then Q, interleaved | LE | none | RTL-SDR `rtl_sdr` |
| `.cs16` | int16, signed | 16 | I then Q, interleaved | LE | none | LimeSDR, USRP export |
| `.cf32` | float32 | 32 | I then Q, interleaved | LE | none | GNU Radio default |
| `.cf64` | float64 | 64 | I then Q, interleaved | LE | none | rare — matlab / scientific dumps |
| `.wav` (float32) | float32 | 32 | I then Q, 2 channels | LE | RIFF header | SDR#, HDSDR |
| `.wav` (int16) | int16 | 16 | I then Q, 2 channels | LE | RIFF header | SDR# lower-precision |
| `.sigmf-data` + `.sigmf-meta` | any (specified in `.sigmf-meta`) | any | I then Q, interleaved | as specified | JSON sidecar | GNU Radio SigMF, community-standard |

Notes:

- **`.iq` is always ambiguous.** Never trust the extension without
  knowing the tool that wrote it. Every discussion below prefers the
  specific extensions.
- **I always comes first.** Interleaving is always `I0 Q0 I1 Q1 …`.
  Any file that swaps the order is nonstandard.
- **`.cu8` is offset-binary.** Values are unsigned with a bias around
  127 or 128. To convert to complex: `(u - 127.5) / 127.5 + 1j *
  (…)`. Forgetting the bias produces a huge DC spike from a mostly-
  correct file — a common "why does my `.cu8` load broken" question.

## Sample-count math

For an interleaved-IQ file, `samples = size_bytes / (2 · bytes_per_sample)`.

- HackRF `.cs8`: `size / 2`
- RTL-SDR `.cu8`: `size / 2`
- LimeSDR `.cs16`: `size / 4`
- GNU Radio `.cf32`: `size / 8`

Duration at sample rate `fs` is `samples / fs` seconds.

## SigMF

SigMF is the emerging community standard for annotated IQ captures.
It pairs a data file (`.sigmf-data`, raw IQ in a specified format)
with a metadata sidecar (`.sigmf-meta`, JSON). Minimum metadata:

```json
{
  "global": {
    "core:datatype": "cf32_le",
    "core:sample_rate": 10000000,
    "core:version": "1.0.0"
  },
  "captures": [
    {"core:sample_start": 0, "core:frequency": 433920000}
  ],
  "annotations": []
}
```

`core:datatype` values follow a `[cf|ci|cu|rf|ri|ru]<bits>_<le|be>`
pattern:

- `cf32_le` — complex float32, little-endian (GNU Radio default)
- `ci16_le` — complex int16, little-endian (`.cs16`)
- `cu8` — complex uint8 (`.cu8`, endianness irrelevant for 8-bit)

Annotations can mark spans of samples with a label and additional
metadata — useful when the capture contains multiple bursts and you
want to name each one.

## HackRF's file convention

`hackrf_transfer` writes and reads interleaved int8 (`.cs8`). Values
range `[-128, +127]`. The `hackrf_transfer` binary does not write any
header or sidecar. Fields to remember out-of-band (or capture with a
SigMF sidecar):

- **center_freq_hz** — what the tune was
- **sample_rate_hz** — needed for time-axis math
- **gains** — LNA, VGA, RF amp — needed for calibrated amplitude
- **timestamp** — the wall clock start of the capture

The `hackrf-agent capture_iq` handler writes both the `.cs8` file
and a JSON sidecar with these fields; see
`src/hackrf_agent/domain/handlers.py`.

## Endianness

Every format listed here is little-endian. Big-endian variants exist
in the wild (SigMF explicitly supports both) but are rare. Symptom of
a byte-swapped file: the spectrum looks mirror-imaged. Fix: swap the
bytes.

```python
raw = np.fromfile('capture.cs16', dtype='>i2')  # big-endian int16
# vs
raw = np.fromfile('capture.cs16', dtype='<i2')  # little-endian int16
```
