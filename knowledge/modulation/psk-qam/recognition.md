# psk-qam/recognition.md — constellation and spectrum tells

## Constant envelope? → PSK. Multi-level envelope? → QAM.

- **BPSK/QPSK/8PSK:** `np.abs(x)` is nearly constant (± the pulse shape's
  small envelope ripple).
- **16/64/256-QAM:** the envelope carries information — histogram of
  `np.abs(x)` shows multiple distinct amplitude levels.

## Constellation viewer

The fastest way to identify a PSK/QAM signal is to look at its
constellation after coarse carrier + timing recovery. Use `SigDigger`
or GNU Radio's `qtgui_const_sink`. What to look for:

- **2 points on the real axis** → BPSK.
- **4 points in a square** → QPSK.
- **8 points on a circle** → 8PSK.
- **16 points in a grid** → 16-QAM.
- **A cloud, no visible structure** → your carrier/timing recovery is
  broken, or it's OFDM (see the OFDM subtopic).

## Spectrum tells

PSK and QAM at the same symbol rate look identical in the spectrum —
both are RRC-shaped with `(1 + α) · Rs` occupied bandwidth. The
constellation is what distinguishes them.

- **α = 0.20:** LTE downlink (per-subcarrier before OFDM).
- **α = 0.35:** DVB-S, most tutorials.

## Eye diagram

Plot successive symbol windows overlaid — a clean "eye opening" tells
you SNR and timing quality. For PSK/QAM:

- **Wide-open eye:** good SNR, tight timing, correct RRC roll-off.
- **Narrow eye:** low SNR or ISI.
- **Eye closed:** hopeless — check carrier phase and timing.

## Confusables

- **QPSK vs OFDM:** OFDM's spectrum is a *flat brick*; QPSK is a
  raised-cosine hump.
- **BPSK vs 2FSK:** BPSK has *constant envelope* AND *constant frequency*
  (only phase moves); 2FSK has *constant envelope* but shifting
  frequency.
- **16-QAM vs OFDM-with-16-QAM-per-subcarrier:** the former is a single
  band with a raised-cosine spectrum; the latter is a flat brick made
  of many 16-QAM subcarriers each ~15 kHz wide.
