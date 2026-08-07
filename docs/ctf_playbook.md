# RF CTF PLAYBOOK

What to do when handed a mystery frequency, a mystery IQ file, or a
"figure out what's on the air" prompt. Optimized for the first 60
seconds.

## Before you touch the HackRF

- **Read the puzzle first.** Is the flag *in the frequency*, *in the
  modulation*, *in a decoded frame*, or *in an interaction*?
- **Confirm the target band.** If it's ADS-B/GPS/airband/marine —
  you're RX-only. Do not attempt TX. The gate will refuse.
- **If TX will be required later** — request a grant now:
  `hackrf-agent grant tx <band> --for <duration>` — before the LLM
  starts trying to compose one implicitly.

Cross-check the band with `knowledge_lookup_band({freq_hz})` first.

## The triage sweep

- `sweep_spectrum({start, end, dwell_s: 1})` at LOW risk.
- Look at the top-N peaks:
  - **Single narrow spike, sustained** → fixed carrier or DC leak
  - **Narrow spike, 30-100 ms bursts, 3-5 repeats** → keyfob
  - **Two parallel narrow spikes** → 2FSK (POCSAG, RTTY)
  - **Wide flat brick** → OFDM (WiFi, LTE, DVB-T)
  - **Dozens of narrow spikes hopping** → FHSS (Bluetooth)
  - **Diagonal streaks** → LoRa CSS chirp
  - **Comb of narrow spikes** → paging batch header

More shapes in `knowledge/ctf/spectrogram-reading.md`.

## Capture-then-analyze

```
capture_iq({target_freq_hz: 433920000, sample_rate_hz: 2000000, duration_s: 1.0})
analyze_iq_modulation({iq_path, sample_rate_hz: 2000000})
analyze_iq_symbols({iq_path, sample_rate_hz: 2000000})
```

- **Use `target_freq_hz`, not `center_freq_hz`.** The tuner offsets
  the LO by `sample_rate/4` so the DC spike lands off your signal.
  See `src/hackrf_agent/ai/prompts.py:110` for the rationale.
- **Sample rate ≥ 4× signal bandwidth.** 2 Msps for narrow bursts,
  8 Msps for wideband.
- **Capture duration ≥ 3-5 bursts** for OOK; ≥ 1 s for paging;
  ≥ 30 s for ADS-B.

## Common puzzle patterns

- **The frequency IS the flag.** Obscure allocation → `knowledge_
  lookup_band` reveals a specific service.
- **The modulation IS the flag.** Unusual FSK deviation or chirp
  slope → `knowledge_lookup_modulation` cross-references.
- **The bitstream IS the flag.** Text, QR, or hash inside a decoded
  packet body → `packet-flag.md`.
- **The timing IS the flag.** Manchester period, PPM ratio, PRI —
  decode without a preconception of what the bytes mean.
- **The replay works or doesn't.** Rolling vs fixed → `unknown-keyfob.md`
  + `replay-vs-analyze.md`.
- **The spectrogram IS the flag.** Image, text, or barcode in the
  waterfall → `waterfall-stego.md`.

## Decode-then-verify

```
knowledge_lookup_protocol({name: "POCSAG"})       # or similar
decode_pocsag({iq_path, sample_rate_hz, baud})    # pick decoder by classification
```

- Always check `crc_ok` (or `invalid_pairs` for Manchester). A
  "decode" without validation is not a decode.
- If the first decoder fails, flip polarity or try a sibling
  decoder before giving up on the classification.

## When to stop

- You've extracted the flag.
- Budget cap reached (`MAX_CAPTURE_MINUTES`).
- You'd need TX in a BLOCKED band — you can't, and that's the
  point of the funnel.

## Cross-references

- `knowledge/ctf/rf-triage.md` — same shape, more detail
- `knowledge/ctf/spectrogram-reading.md` — shapes → suspects
- `knowledge/ctf/packet-flag.md` — flag-in-frame patterns
- `knowledge/iq-analysis/walkthrough.md` — worked example
- `docs/rf_cheatsheet.md` — band + modulation + line-code reference
- `docs/safety.md` — before recommending TX
