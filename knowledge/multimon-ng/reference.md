# multimon-ng/reference.md — the CLI surface

## Input

- **File:** `multimon-ng something.wav`. Must be 22050 Hz, mono,
  signed 16-bit PCM.
- **Stdin (raw):** `-t raw` reads raw signed-16 samples from stdin.
- **Multiple modes:** `-a MODE1 -a MODE2 ...` decodes in parallel and
  labels output.

## Supported modes (the ones you care about)

- **POCSAG512, POCSAG1200, POCSAG2400** — paging. 2FSK from a
  discriminated audio stream.
- **FLEX** — the Motorola successor to POCSAG, 4FSK.
- **DTMF** — telephone touchtones (7 kHz spectrum).
- **ZVEI, EEA, EIA** — European emergency-service selective-calling
  tone sequences.
- **AFSK1200, AFSK2400** — Bell 202 modem style; the audio layer of
  AX.25 packet radio at 1200 baud.
- **X10** — over the 121 kHz powerline carrier (weird niche).
- **SCOPE, SCOPE_LEFT, SCOPE_RIGHT** — visualization aids, not
  decoders.

## Output

- Plaintext line per decoded packet: `POCSAG1200: Address: 1234567
  Function: 0 Alpha: hello world`.
- FLEX includes channel and cycle info.

## Typical pipeline (POCSAG)

```
# 1. HackRF captures at 2 Msps NFM around the pager band
# 2. GNU Radio flowgraph: HackRF -> FM demod -> resample to 22050 -> WAV
# 3. Feed WAV to multimon-ng:
multimon-ng -a POCSAG512 -a POCSAG1200 -a POCSAG2400 -a FLEX pager.wav
```

Or, live from an rtl-sdr / HackRF via osmocom + rtl_fm equivalent:

```
rtl_fm -f 152.007M -s 22050 - | multimon-ng -t raw -a POCSAG1200 /dev/stdin
```

## When to reach for something else

- Not audio-shaped: use rtl_433, GNU Radio, or SDRAngel.
- POCSAG through **encrypted** talkgroups: multimon-ng gives the
  ciphertext bits; decryption is out of scope.
- Voice trunking (DMR, P25, TETRA, NXDN): reach for `DSD+` or
  `SDRTrunk` from a discriminated audio stream.

## Citations

- multimon-ng GitHub (EliasOenal/multimon-ng).
- ITU-R M.584-2 (POCSAG spec).
