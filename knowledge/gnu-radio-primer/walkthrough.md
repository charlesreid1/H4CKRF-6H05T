# gnu-radio-primer/walkthrough.md — three canonical flowgraphs

Assume GNU Radio 3.10+. Every graph below is small enough to draw in
GRC in <10 minutes.

## Flowgraph 1 — Broadcast FM RX to WAV

Blocks:

1. `osmocom Source` — device args `hackrf=0`, sample rate 2.4 MHz,
   center freq 97.3 MHz (tune to a local FM station), LNA 24, VGA 20.
2. `Rational Resampler` — down to 250 kHz (interp 5, decim 48).
3. `Quadrature Demod` — gain `250_000 / (2·pi·75_000)` for wideband FM.
4. `Rational Resampler` — down to 48 kHz for audio (interp 48, decim 250).
5. **De-emphasis:** a `Single Pole IIR Filter` with `alpha = 1 -
   exp(-1 / (48_000 · 75e-6))`.
6. `WAV File Sink` — 48000 Hz, mono, `fm_broadcast.wav`.

Run for ~10 seconds, play the WAV. If you hear the station, congrats —
you have the world's most convoluted FM radio.

## Flowgraph 2 — 433 MHz OOK envelope analyzer

Blocks:

1. `File Source` — `.cs8` capture at 2 Msps, 433.92 MHz.
2. `Complex to Mag` — the envelope.
3. `QT GUI Time Sink` — visualize the envelope stream.
4. `Threshold` — `low = 0.05`, `high = 0.15` (adjust in real time).
5. `File Sink (unsigned char)` — bit stream at 2 Msps.

You now have a binary stream. Downsample by `sps` (samples per bit)
externally with a numpy script, then Manchester-decode.

## Flowgraph 3 — POCSAG pipeline to multimon-ng

Blocks:

1. `osmocom Source` — HackRF, 2 Msps, center 152.007 MHz (or wherever
   your local pager network runs).
2. `Frequency Xlating FIR Filter` — LPF with 12.5 kHz cutoff, offset
   0 (or nudge to the exact pager carrier).
3. `Rational Resampler` — to 22050 Hz.
4. `Quadrature Demod` — gain tuned so ±4.5 kHz deviation covers full
   scale.
5. `Multiply Const` — `32000` for gain into a 16-bit WAV.
6. `WAV File Sink` — `pocsag.wav`.

Pipe the WAV in real time to `multimon-ng`:

```
multimon-ng -a POCSAG1200 -a POCSAG2400 pocsag.wav
```

(In practice, avoid a `WAV File Sink` for streaming — use a `File Sink`
writing raw int16 and pipe with `-t raw`.)

## From GRC to Python

Save any flowgraph as `.grc`, generate Python:

```
grcc top_block.grc  # produces top_block.py
python top_block.py
```

Edit the generated Python if you need programmatic control (loops,
sweeps, parameter changes). For CTF triage this is often the fastest
iteration path.
