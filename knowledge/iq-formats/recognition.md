# iq-formats/recognition.md — how to spot format problems

## Huge DC offset in a `.cu8` load

You loaded RTL-SDR `.cu8` as if it were `.cs8`, or you forgot the
127.5 bias.
**Test:** compare `x.mean()` — if `|mean(x)| > 0.5`, the bias is
uncorrected. Fix by re-loading with the correct dtype/bias.

## Spectrum looks mirror-imaged

Every real signal you expected at `+f` appears at `-f`. The dtype
loaded was byte-swapped, or the I/Q channels got swapped.
**Test:** re-load with `>` (big-endian) vs `<` (little-endian) numpy
dtype specifiers, or swap I and Q:

```python
x_alt = x.imag + 1j * x.real
```

If `x_alt` shows the expected spectrum, someone wrote the file with
Q-then-I ordering.

## Duration doesn't match expected size

You expect a 2-second capture at 10 Msps: `2 × 10e6 × 2 = 40 MB` for
`.cs8`. The file is 80 MB. Either `sample_rate` was double what you
assumed, or the file is actually `.cs16` (16-bit) mislabeled as
`.cs8`.
**Test:** load with both dtypes; the one with a well-shaped spectrum
is correct.

## Clipping in a `.cf32`

Real files should have `|x| ≤ 1.0` if the writer normalized.
`np.max(np.abs(x)) > 1.0` means either no normalization, or the
capture actually saturated the ADC (flat-topped envelope).
**Test:** if `|x|` maxes at exactly some round number (e.g. exactly
`127` in a `.cf32` that came from a `.cs8`), the writer forgot to
scale.

## WAV file that "sounds like noise" but contains IQ

Loading an IQ-WAV in an audio player produces noise — not a bug.
IQ-in-WAV is a container hack; the "audio" is complex baseband, not
audio.
**Test:** load with `scipy.io.wavfile.read`, check the stereo/IQ
convention (channel 0 = I, channel 1 = Q), and treat as complex.

## SigMF sidecar disagrees with data

`.sigmf-meta` claims `sample_rate = 2e6`, but the burst structure in
`.sigmf-data` implies 10 Msps. The metadata lies.
**Test:** cross-check with any other known fact — a burst period that
matches a known protocol's symbol rate at only one of the candidate
`fs` values is a strong signal.

## Bit-count intuition

For a HackRF capture that looks quantized in histograms of `x.real`:

- Bins spaced by `1/128` → 8-bit source (correct for HackRF)
- Bins spaced by `1/32768` → 16-bit source (`.cs16`)
- Continuous → 32-bit source (`.cf32`, or `.cs*` that's been
  low-pass-filtered post-load)

If a supposed 8-bit HackRF file shows continuous values, someone
processed it after capture — probably applied a filter or a rescale.
