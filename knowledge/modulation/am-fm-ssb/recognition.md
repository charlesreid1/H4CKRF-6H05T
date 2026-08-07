# am-fm-ssb/recognition.md — spot analog modulations on a waterfall

Fast triage — you have 60 seconds and a spectrogram.

## AM

- **Central carrier line** (bright, narrow, at the exact tuned frequency).
- **Symmetric sidebands** on either side that mirror each other.
- **Audio-modulation shape:** sidebands pulse in time with the audio.
- **Envelope tells you it's AM:** `np.abs(x)` shows an audio-like waveform.

## FM

- **No central carrier line** — energy is spread by deviation.
- **Constant envelope** — `np.abs(x)` is flat.
- **Bell-shaped occupied bandwidth:** narrow at rest, blooms wider on
  audio peaks.
- **Broadcast FM: ~200 kHz per channel.** Narrow-FM voice: ~15 kHz.

## SSB

- **Only one sideband** — no mirror image on the other side of the LO.
- **No carrier line.** Cleaner-looking than AM on a spectrogram.
- **Envelope carries audio content** (like AM), so `np.abs(x)` is
  audio-like.
- **Voice ~2.7 kHz wide** in the occupied direction.

## Confusables

- **AM vs narrow FM at low SNR:** AM has a carrier line; narrow FM
  doesn't. If you're not sure, envelope-detect: audio → AM.
- **SSB vs CW (Morse):** SSB voice fills a ~2.7 kHz bandwidth
  continuously; CW is a narrow tone that keys on and off.
- **Broadcast FM vs a DAB block:** FM is a single ~200 kHz Bell shape;
  DAB is a flat 1.5 MHz brick.
