# two-tone-cipher — DTMF-like keying as a puzzle

Some CTFs hide the flag as a sequence of tones — one or two audio
frequencies used as keying symbols.

## The signature

- Two narrow spectral peaks in the audio band (300-3000 Hz).
- Short bursts (~50-200 ms) with silence between.
- Sometimes single-tone (Morse-like) rather than two-tone (DTMF).

## Common two-tone systems

- **DTMF (dual-tone multi-frequency).** 4×4 matrix of frequency
  pairs, digits 0-9 and A-D. Widely used in telephony. Decode by
  FFT'ing short windows and matching the top-2 peaks to the DTMF
  table.
- **RTTY.** Baudot ITA2 over 2FSK (mark/space at 1275/1445 Hz or
  1615/1785 Hz for amateur radio). H4CKRF has `decode_rtty`.
- **PSK31.** Phase-shift keying at 31.25 baud for amateur digital
  modes. Not in H4CKRF's decoder set; escalate to `fldigi`.
- **Morse (CW).** Single-tone, on-off keyed at 5-40 wpm. H4CKRF does
  not decode Morse today; recognizable from the dot/dash timing.

## The workflow

1. **FM demod** the capture — DTMF is audio inside an FM carrier.
   Use `analyze_iq_modulation` to confirm FM/AM.
2. **FFT short windows** of the audio (~30 ms each) — the top two
   peaks give the DTMF digit.
3. **Look up the digit table** — 697/770/852/941 Hz rows × 1209/1336
   /1477/1633 Hz columns.

The H4CKRF stack does not ship a DTMF decoder today. The operator
uses `multimon-ng` after FM-demod'ing the capture.

## Trap catalog

- **"Every two-tone burst is DTMF."** False. Could be pager
  selective-call (Motorola Quik-Call, Plectron), RTTY, or a novel
  cipher.
- **"The digits are the flag."** Sometimes; often the digits map to
  ASCII characters via A1Z26 or a different encoding.
- **"Silence gaps are noise."** Sometimes the *gaps* encode data
  (Morse code lives in the gap durations).

## Failure modes

- **Wrong FM deviation.** Discriminator produces noise if you
  demodulate a wideband FM as narrowband or vice versa. Check the
  spectrogram for peak-to-peak deviation.
- **Off-frequency capture.** DTMF tones drift into unhelpful FFT
  bins if the capture is off-center; recapture with `target_freq_hz`.

## Cross-references

- `../modulation/` — 2FSK vs AM discrimination
- `../pocsag-flex/` — 2FSK paging is a special case
- `numbers-station-decode.md` — HF single-tone flavor
