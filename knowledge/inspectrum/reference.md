# inspectrum/reference.md — cursors that measure

## What inspectrum does

- **Wide-view spectrogram** with adjustable FFT size, window (Hann/
  Hamming/Blackman-Harris/etc.), and colormap.
- **Frequency cursor:** drag a horizontal cursor across the spectrogram
  to read the frequency (Hz relative to center) at any row.
- **Time cursor:** drag a vertical cursor to read the elapsed time.
- **Symbol-rate cursor:** drag between symbol boundaries and inspectrum
  reports the resulting symbol rate (given the sample rate).
- **Frequency estimator:** click a peak to snap the cursor to the
  centroid of the surrounding energy.

## File formats

- `.cs8`, `.cs16`, `.cf32` — bare IQ.
- `.complex` — URH-native complex64.
- SigMF paired files.

## When to reach for inspectrum vs URH

- **URH:** editable + auto-detect + full workflow (bits, decoding,
  diff, export).
- **inspectrum:** precision measurement of a *single* signal parameter
  without side effects. Use it to *check* URH's auto-detect: does the
  measured symbol rate match URH's guess?

## Typical uses

- Measure symbol rate on an unknown 2FSK burst — cursor-drag between
  two symbol boundaries → symbol rate readout.
- Measure carrier offset from tuned frequency — cursor at the actual
  peak vs the tuned center.
- Estimate SNR by comparing peak PSD to noise-floor PSD.
- Confirm cyclic-prefix duration on an OFDM burst by inspecting
  successive-symbol edges.

## Citations

- inspectrum GitHub (miek/inspectrum).
