# dsp/recognition.md — how a spectrogram lies to you

You will be reading spectrograms. Every artifact below has fooled
somebody.

## Spectral leakage

Without windowing, an FFT of a finite window smears energy from a
tone into the neighboring bins ("sinc-shaped skirts"). Two tones
close in frequency can look like one. Fix: apply a Hann or
Blackman-Harris window before the FFT.

## Scalloping loss

A tone that lands exactly between two FFT bins is attenuated up to
~3.9 dB (rectangular window) or ~1.4 dB (Hann). Consequence: peak
picking without interpolation over-reports quiet signals as much as
4 dB below their true power.

## The DC spike

A line at exactly 0 Hz (i.e. at the tune frequency) that persists
across every capture and looks unusually narrow. Origin: LO leakage
into the mixer + amplifier DC offset, filtered through the ADC's
zero-frequency response. It is **not a signal**. It is the reason
`target_freq_hz` exists — offsetting the tune moves your real signal
out from under it.

## IQ imbalance — the mirror image

If the I and Q channels don't have matched amplitude and 90° phase,
every tone at `+f` gets a partial ghost at `-f`. Perfect balance =
0 dB image rejection. Consumer SDRs typically achieve 30–40 dB with
factory calibration. Fix: run an IQ-imbalance correction (see
`../sdr-fundamentals/walkthrough.md`).

## ADC clipping

A flat-topped envelope in the time domain, or a broadband raise of
the noise floor across the whole span. The HackRF is 8-bit —
dynamic range is only ~48 dB SFDR — so a strong nearby signal (e.g.
FM broadcast at 3 miles) can clip the ADC and appear to "spray"
across the band. Fix: back off the LNA/VGA gain; use a bandpass
filter at the antenna.

## LNA compression

Sharp spurs at harmonics of a strong in-band signal, or at
intermodulation products between two strong signals. Symptom: turn
the LNA down and the spurs disappear (a real signal doesn't).

## USB-2 backpressure

At high sample rates (>16 Msps on some hosts), the HackRF can drop
samples if USB 2.0 can't keep up. On a spectrogram this looks like a
horizontal streak or a sudden apparent frequency shift at the moment
of the drop. Fix: run at a lower sample rate, or use a host with
better USB scheduling.

## Aliased images

A signal well outside the tuned span sometimes shows up folded into
the span (imperfect anti-alias, or intentional under-sampling). The
tell: retune ±1 MHz and see if the image moves in the opposite
direction from a real signal.

## Window-scalloping vs actual notch

A real notch (from a coax stub filter, a strong reflector, etc.) is
persistent across time. A window-scalloping notch depends on your
FFT bin alignment — retune slightly and it moves. Use this to tell
which one you're looking at.
