# numbers-station-decode — HF-flavored puzzles

A "numbers station" is a shortwave broadcast reading strings of numbers
(often in synthetic voice). Real ones are intelligence traffic; CTF
ones ship the flag as one of the strings.

## The signature

- **HF band (3-30 MHz).** The HackRF alone can't tune this — you're
  either given a capture at IF or told to work off a WebSDR archive.
- **Single-carrier AM voice** or **SSB voice** (single-sideband).
- Strings of digits, letters, or phonetic alphabet spoken/keyed at
  regular intervals.

The H4CKRF stack is 30 MHz to 6 GHz; HF work usually happens with an
RTL-SDR + upconverter or on a WebSDR. This file exists so the
assistant knows what the shape looks like when handed a capture.

## Common flavors

- **Enigma / Cynthia.** Female voice reading five-digit groups in
  English or Spanish. Historical.
- **Yosemite Sam / Backwards Music Station.** Recorded music
  fragments used as null / cover traffic.
- **HM01.** Cuban numbers station using MFSK-32 data bursts between
  voice sections.
- **CIS Music Station / S06.** Russian, single-frequency AM.

## The workflow

1. **AM/SSB demod** the capture into audio.
2. **Read the digits.** Manual transcription or OCR-style
   speech-to-text.
3. **Decode.** Digits may be A1Z26 → letters; groups of five may be
   one-time-pad ciphertext (unbreakable without the pad); or the
   digits themselves are the flag (usually a hex or ASCII code).

## Trap catalog

- **"Every numbers station has a hidden message."** False. Some are
  cover traffic. The CTF version *does* have a flag; real-world
  numbers stations often don't decrypt to plaintext even with the
  pad.
- **"MFSK looks like FSK."** True at first glance; the number of
  tones (2, 4, 8, 16, 32) distinguishes them. Check the top-N peaks
  in the FFT.

## Failure modes

- **Wrong sideband.** USB vs LSB matters for SSB. Try both.
- **Timing / speed drift.** HF propagation stretches the audio when
  the ionosphere shifts. Some captures are unusable at the top of a
  band during an ionospheric event.

## Cross-references

- `../satellite/` — for HF-adjacent decode workflow
- `../modulation/` — AM vs SSB vs MFSK
- `two-tone-cipher.md` — related audio-frequency-encoding techniques
