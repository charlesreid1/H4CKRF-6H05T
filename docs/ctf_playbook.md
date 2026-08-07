# RF CTF PLAYBOOK

What to do when handed a mystery frequency / a mystery IQ file / a
"figure out what's on the air" prompt. Optimized for the first 60
seconds. Placeholder — fills in as we accumulate recipes.

## Before you touch the HackRF

- Read the puzzle. Is the flag *in the frequency*, *in the
  modulation*, *in a decoded frame*, or *in an interaction*?
- Confirm the target band. If it's ADS-B/GPS/airband — you're
  RX-only. Do not attempt TX. The gate will refuse.
- If TX will be required later — request a grant now with
  `hackrf-agent grant tx <band> --for <duration>` — before the LLM
  starts trying to compose one implicitly.

## The triage sweep

- `sweep_spectrum(start, end, dwell_s=1)` at LOW risk.
- Look at the top-N peaks. Which occupancy pattern do you see?
  - Single narrow spike → likely a fixed carrier or a keyfob quiet
  - Wide flat brick → OFDM (WiFi, LTE downlink, DVB-T)
  - Dozens of narrow spikes → FHSS (Bluetooth, some LoRaWAN)
  - Two side lobes near a center → 2FSK or ASK/OOK
  - Symmetric multi-peak comb → paging (POCSAG/FLEX)

## Capture-then-analyze

- `capture_iq(target_freq_hz=…, sample_rate_hz=…, duration_s=…)` —
  use `target_freq_hz` not `center_freq_hz` to keep the DC spike off
  your signal (see `src/hackrf_agent/ai/prompts.py:110` for the reason).
- `analyze_iq_modulation(iq_path)` → what modulation family does the
  DSP suggest? *(planned — see [../plan-organization.md](../plan-organization.md))*
- `analyze_iq_symbols(iq_path)` → symbol rate + timing recovery.
- `decode_manchester(iq_path)` / `decode_pwm(iq_path)` → bits.

## Common puzzle patterns

- The frequency IS the flag (obscure allocation → look it up)
- The modulation IS the flag (unusual FSK deviation → clue)
- The bitstream IS the flag (decoded packet contains text/QR/hash)
- The timing IS the flag (Manchester period, PPM ratio)
- The replay works or doesn't (rolling vs fixed code — see `knowledge/keyfobs/`)
- The spectrogram IS the flag (image-in-waterfall stego)

## When to stop

- You've extracted the flag.
- Budget cap reached (`MAX_CAPTURE_MINUTES`).
- You'd need TX in a BLOCKED band — you can't, and that's the
  point of the funnel.
