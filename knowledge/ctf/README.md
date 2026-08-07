# ctf/

CTF puzzle patterns. One file per subgenre. Each names the signature
you look for, the decoder pipeline, and the flag-hiding pattern.

## Triage layer

- `rf-triage.md` — first 60 seconds with a mystery signal
- `spectrogram-reading.md` — what a spectrogram tells you
- `signal-classification.md` — the flag is the modulation name

## Sub-GHz puzzles

- `unknown-keyfob.md` — is it fixed, rolling, or novel?
- `garage-door-forensics.md` — Chamberlain / Genie / Nexa reverse
  engineering from three captures
- `weather-station-flag.md` — an authentic-looking Acurite / Fine
  Offset packet with a payload twist
- `replay-vs-analyze.md` — when to reach for replay vs when to decode

## Spread-spectrum puzzles

- `lora-flag.md` — LoRa chirp with a flag in the dechirped payload
- `frequency-hop-flag.md` — hop pattern encodes the flag

## Aviation / paging RX-only

- `ads-b-recon.md` — an aircraft's squawk or callsign is the flag
- `paging-decode.md` — POCSAG / FLEX with a plaintext flag

## Steganography-flavored

- `waterfall-stego.md` — an image hidden in the spectrogram
- `spectrum-map-flag.md` — the SHAPE of the spectrogram IS the flag
- `two-tone-cipher.md` — DTMF-like keying used as a cipher
- `numbers-station-decode.md` — HF numbers-station flavor

## Framing / integrity puzzles

- `packet-flag.md` — the flag is inside a decoded frame
- `crc-audit.md` — which packets pass CRC is the flag
- `whitening-audit.md` — a bit-scrambler is applied and must be reversed

Complements the fast-lookup `docs/ctf_playbook.md` in the top-level docs.
