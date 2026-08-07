# spectrogram-reading

The spectrogram is the CTF's most information-dense artifact. Reading
it well often solves the puzzle without any decode step.

## Axes

- **Horizontal.** Time.
- **Vertical.** Frequency.
- **Color / intensity.** Power.

`analyze_iq_spectrogram` returns *per-slice peaks* (one point per
time-slice), not the full color plot. The picture is reconstructed from
those points.

## Shapes to recognize

- **Narrow vertical line.** CW carrier, unmodulated LO leak, or DC
  spike.
- **Fat vertical line, seconds long.** FM voice with a whistle.
- **Short (10-100 ms) horizontal streaks with gaps.** Keyfob or
  weather-station burst.
- **Two parallel lines close together.** 2FSK — the two tones sit
  ± deviation from the carrier.
- **Wide flat "brick" for tens of milliseconds.** OFDM (WiFi, LTE,
  DVB-T).
- **Diagonal streaks, evenly spaced.** LoRa chirp — the slope encodes
  the spreading factor.
- **Comb of narrow lines equally spaced.** Multi-tone signal, or
  IQ-imbalance mirroring (real signal + mirror across DC).
- **Slow modulation of a carrier's amplitude.** AM — voice or SSTV.

## Stego signatures

- **Image in the waterfall.** Rare-but-fun — the transmitter is
  amplitude-modulating a carrier at a precise pattern so the FFT bins
  spell text or draw an image. Look for suspiciously "clean" vertical
  bands with no radio-plausible spacing.
- **Barcode.** Very narrow bursts, uniformly spaced. Read the pattern
  as a bitstream.
- **Text as tones.** RTTY, Morse, PSK31 — see
  `numbers-station-decode.md`.

## Colormap and dynamic range

- H4CKRF returns dBFS values. Zero dBFS is full-scale; anything below
  the noise floor is "just noise."
- The HackRF's 8-bit ADC has ~48 dB of usable dynamic range. If two
  peaks are more than 48 dB apart, the weaker one is invisible; drop
  gain to see it.

## What to do next

Given the shape, look up the suspect protocol:

- Keyfob-burst shape → `../keyfobs/`
- 2FSK two-line signature → `../pocsag-flex/` or `../modulation/`
- LoRa diagonal → `../lora/`
- OFDM brick → `../ism-2400/` (WiFi) or handoff
- Image-in-waterfall → `waterfall-stego.md`

## Cross-references

- `../iq-analysis/recognition.md` — same shapes, more measurements
- `records/known_signals.json` — searchable via `knowledge_explain_signal`
