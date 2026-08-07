# iq-analysis — reference

The numeric spec for what `analyze_iq_*` and `read_iq_summary` do and why
their outputs look the way they do.

## Waterfall (spectrogram) reading

A spectrogram is a stack of short-time FFTs plotted with time on one axis,
frequency on another, and power as color. Two knobs matter:

- **FFT size (`fft_size`).** Trades frequency resolution against time
  resolution. `Δf = fs / fft_size`; `Δt = fft_size / fs`. Double one, halve
  the other. Default `1024` at 2 Msps → `Δf ≈ 1.95 kHz`, `Δt ≈ 0.5 ms`.
- **Overlap.** 50% is the standard compromise. 75% smooths transients but
  quadruples compute; 0% (no overlap) misses events shorter than one FFT
  window.

`analyze_iq_spectrogram` returns *per-slice peaks*, never the full FFT
matrix. Each slice reports `(peak_freq_hz, peak_dbfs, timestamp_s)`. The
LLM composes the picture from that summary — the raw matrix would flood
the context window.

## Symbol-timing recovery

Given a demodulated envelope (or magnitude, or instantaneous frequency),
recover the symbol clock so bits can be sliced from samples.

Three canonical algorithms:

- **Gardner** — for BPSK/QPSK, uses the mid-symbol and symbol-transition
  samples. Robust for medium-SNR; slow to converge.
- **Mueller-Müller** — for PAM-like signals, uses two-sample memory.
  Widely used in `gr-osmosdr` for OOK slicing.
- **Zero-crossing / edge-interval** (what `analyze_iq_symbols` does today) —
  find rising/falling edges after envelope-slicing, cluster the intervals,
  the peak of the histogram is the symbol period.

Edge-interval is cheap and works for anything with a preamble; Gardner
and Mueller-Müller need PSK/QAM and matched filtering.

## Clock-recovery basics

Once symbol timing is known, phase-lock the receiver's clock so drift
doesn't drop bits across a long frame:

- Track edge times relative to expected symbol boundaries.
- Advance/retard by a small fraction (μ) proportional to the error.
- The loop bandwidth trades acquisition speed against jitter.

For most H4CKRF CTF-scale captures (< 1 s), a fixed clock estimate from
`analyze_iq_symbols` is enough. Only long captures (PSK, LoRa) need a real
PLL.

## SNR estimation

Two useful proxies without a clean reference:

- **Peak-to-noise-floor** — take the top-N FFT bins as signal, the
  median as noise floor. Cheap, but conflates signal peaks and CW jammers.
- **M2/M4 moments** — E[|x|²] / (E[|x|]²) for a constant-envelope signal
  should approach 1; anything larger is noise. Numerically ugly at low
  SNR.

`read_iq_summary` reports both the noise floor and the strongest peak, so
"peak minus floor" is a fair back-of-the-envelope SNR estimate.

## `read_iq_summary` output cheatsheet

The verb returns a dict shaped roughly:

```jsonc
{
  "iq_path": "...",
  "num_samples": 2_000_000,
  "sample_rate_hz": 2_000_000,
  "duration_s": 1.0,
  "noise_floor_dbfs": -70.0,
  "peak_dbfs": -25.0,
  "peak_freq_hz": 433_920_000,
  "occupancy_pct": 2.1
}
```

- `occupancy_pct` — fraction of FFT bins > (noise_floor + 6 dB). Below
  1% is empty; above 30% is a wideband signal or your gain is wrong.
- `peak_freq_hz` — the strongest bin's absolute frequency, mapping the
  FFT bin back through `center_freq_hz` + bin offset.

## Cross-references

- `analyze_iq_modulation` bins into candidate families using moments
  computed here; see `knowledge/modulation/reference.md`.
- `analyze_iq_symbols` returns the same `(rate, confidence)` schema
  described above; see `knowledge/demodulators/reference.md`.
- Every downstream `decode_*` verb consumes symbol-rate output.
