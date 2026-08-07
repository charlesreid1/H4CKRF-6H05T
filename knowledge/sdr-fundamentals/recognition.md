# sdr-fundamentals/recognition.md — hardware pathologies at a glance

Pattern → probable cause → fix.

## Sharp narrow spike at 0 Hz (or at `center_freq_hz`)

**Cause:** DC spike (LO leakage + amp DC offset).
**Fix:** use `target_freq_hz` at capture time. Post-hoc: high-pass
filter or notch, but you can't recover ADC dynamic range consumed by
the spike.

## Mirror image around 0 Hz

Every real signal at `+f` has a faint copy at `-f`. Suspiciously
symmetric spectrum.
**Cause:** IQ imbalance.
**Fix:** run a rebalance step (`../walkthrough.md#2`). Consumer SDRs
top out at ~40 dB image rejection.

## Flat-topped envelope, broadband noise-floor raise

Time-domain envelope hits a ceiling; frequency domain shows a lifted
noise floor across the whole span.
**Cause:** ADC clipping. A strong signal (in-band or a strong
adjacent-channel bleedthrough) is saturating the 8-bit ADC.
**Fix:** reduce gain (turn RF amp off first, then drop LNA). Add an
external bandpass filter if the offender is out-of-band.

## Spurs at harmonics or intermodulation products

Extra tones at integer multiples of a real strong signal, or at
`f1 ± f2`, `2f1 ± f2`, etc.
**Cause:** LNA compression. Front end is nonlinear at the drive
level.
**Fix:** back off the LNA.

## Sudden horizontal streak in the spectrogram

Everything appears to smear or shift for a few samples.
**Cause:** USB-2 sample drop. Host couldn't drain the FIFO fast
enough at the requested sample rate.
**Fix:** lower `sample_rate_hz`, or move to a host with better USB
scheduling. If persistent at high rates, use decimation on-device
via `hackrf_transfer` and re-capture at a lower rate.

## Persistent narrow tone that shifts with tuning

A tone that follows the tune frequency by a fixed offset (e.g. always
0.5 MHz above wherever you tune).
**Cause:** spurious internal mixing product. Often the reference
clock leaking through the mixer.
**Fix:** check external clock discipline; the HackRF's TCXO can be
disciplined by a GPSDO.

## Signal apparently at a "wrong" frequency

You aim at 433.92 MHz, you see the signal at 431.42 MHz in the file.
**Cause:** `target_freq_hz` offset not accounted for downstream.
`center_freq_hz` in the resulting file is `target_freq_hz` (post
frequency-shift), so downstream tools should treat the file as
centered on the target.

## Very quiet baseline, a wall of noise, no signals visible

Antenna isn't connected, or you're using a charge-only USB cable and
the device isn't fully powered.
**Fix:** check `hackrf_info` returns firmware and serial cleanly; try
another USB cable/port.
