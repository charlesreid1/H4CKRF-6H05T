---
name: hackrf
description: Use whenever an operator's question or request touches RF, IQ, HackRF, a specific frequency, a modulation family, keyfobs, paging (POCSAG/FLEX), APRS, RTTY, or any signal on the air. Backed by the `hackrf-agent-mcp` server — one safety-gated tool, `execute_command`, that funnels every RF action through a deterministic risk/approval/audit chain.
---

# HackRF co-pilot SKILL

## When to reach for this MCP

If the operator's question or request touches any of these, this MCP
is the tool:

- A specific frequency or band ("what's on 433.92?", "sweep 900-930")
- Modulation theory (OOK vs FSK, what QPSK looks like, chirp CSS)
- Keyfobs, TPMS, garage doors, weather stations
- Paging (POCSAG/FLEX), APRS, RTTY, AX.25 packet
- ADS-B / Mode S (RX-only) or AIS ship tracking
- A captured `.iq` file the operator wants analyzed or decoded
- Any transmit action on the HackRF (subject to the funnel)

Do not attempt to reason about RF signals from model weights when the
MCP can answer from the corpus or the DSP tier. If a
`knowledge_lookup_*` or `decode_*` verb exists for the question,
prefer it over free-form recall.

## How the funnel works

There is one tool: `execute_command`. Every call is discriminated by
`action`. Three tiers of verbs, all funneling through the same
`CommandExecutor` chokepoint:

### Know — corpus retrieval (all LOW risk, all read-only)

- `knowledge_list_topics` — enumerate every topic dir + its files
- `knowledge_read` — return one `<topic>/<name>.md` file
- `knowledge_search` — case-insensitive substring across the corpus
- `knowledge_random` — surprise-me: one random markdown file (optional
  deterministic seed)
- `knowledge_lookup_band` — given `freq_hz`, return the `bands.json`
  record(s)
- `knowledge_lookup_modulation` — given a family name, return the
  `modulations.json` record
- `knowledge_lookup_protocol` — given a protocol name (POCSAG, AX.25,
  LoRaWAN, …), return the `protocols.json` record
- `knowledge_lookup_keyfob` — given vendor and/or model, return
  matching keyfob-system records with fixed/rolling + crypto notes
- `knowledge_lookup_decoder` — given a decoder-family name (Manchester,
  NRZ, PWM, PPM), return the `decoders.json` record with the paired
  `analyze_iq_*` / `decode_*` verb
- `knowledge_bibliography` — resolve one citation, or list all
- `knowledge_explain_signal` — given freq/bw/modulation hints, rank
  candidates from `known_signals.json`
- `knowledge_cross_reference` — walk `see_also` across every records
  file, returning the root + resolved references
- `knowledge_verify_claim` — grade a claim against the trap catalog

### Analyze — offline DSP (all LOW risk, cannot touch libhackrf)

- `analyze_iq_modulation` — moment-based classifier over a `.iq` file
- `analyze_iq_symbols` — edge-interval symbol-rate estimator
- `analyze_iq_spectrogram` — compact per-slice peak-freq + power
- `decode_manchester`, `decode_pwm`, `decode_ppm`, `decode_nrz` —
  line-code decoders
- `decode_pocsag` — POCSAG paging (baud 512/1200/2400)
- `decode_ads_b` — Mode S extended squitter (sample_rate ≥ 2 MHz)
- `decode_rtty` — Baudot ITA2 over 2FSK
- `decode_ax25` — HDLC packet radio (Bell 202 AFSK-1200 or FSK-9600)
- `decode_aprs` — AX.25 UI frames with APRS payload interpretation

### Act — the HackRF surface (funnel with risk classification)

- `get_device_info`, `sweep_spectrum`, `capture_iq`, `transmit_iq`,
  `read_iq_summary`, `decode_ook`, `grant_list`, `audit_query`

TX actions go through `RiskAssessor` → optional
`PermissionService.check` → optional `ApprovalPort.request`. TX in a
BLOCKED band is refused deterministically.

Read `docs/safety.md` before recommending TX. Never propose that the
operator "just try it" on a blocked band — the gate will refuse and
it is correct to refuse.

## Corpus depth cues

Every `knowledge/<topic>/` typically ships:

- `README.md` — orient
- `reference.md` — numbers-dense technical spec
- `walkthrough.md` — worked examples (when the topic warrants)
- `recognition.md` — how to spot this in a waterfall (load-bearing
  for triage)

Prefer `walkthrough.md` when the operator is *doing* rather than
reading. Prefer `recognition.md` when the operator has a spectrogram
or capture and is asking "what is this?"

Numeric claims should route through `knowledge_lookup_band`,
`knowledge_lookup_modulation`, and the shared `knowledge_verify_claim`
sanity check. Free-form `knowledge_search` is a last resort.

## Playbook — you've been handed a mystery frequency

1. **Look up the band.** `knowledge_lookup_band(freq_hz=…)`. If
   `blocked_tx=true` in the response, plan for RX-only from the
   start.
2. **Sweep.** `sweep_spectrum` over the target range. Match the
   occupancy pattern against `docs/ctf_playbook.md`.
3. **Capture.** `capture_iq` using `target_freq_hz` (not
   `center_freq_hz`) so the DC spike lands off your target.
4. **Analyze.** `analyze_iq_spectrogram` for a visual → `analyze_iq_modulation`
   → `analyze_iq_symbols`.
5. **Decode.** Pick the right `decode_*` verb based on the
   modulation:
   - OOK Manchester keyfob → `decode_manchester`
   - PWM keyfob (older Chamberlain) → `decode_pwm`
   - POCSAG paging → `decode_pocsag`
   - RTTY (2FSK, Baudot) → `decode_rtty`
   - AX.25 packet → `decode_ax25` or (with APRS payload)
     `decode_aprs`
   - ADS-B → `decode_ads_b`
6. **Verify.** Cross-check the result against `knowledge_lookup_protocol`
   before claiming "this is POCSAG at 1200 baud" or "this is Keeloq."

## The funnel invariant

You never see libhackrf. Every RF action is `execute_command`.
Trying to bypass the gate is a bug in reasoning, not a bug in the
gate. If a capability seems missing, the fix is to propose a new
`CommandAction` value with a deterministic risk classification —
never a second tool that reaches around the funnel.

## Compliance reminders

- **Never TX in a BLOCKED band.** The RiskAssessor's list is
  hardcoded in `src/hackrf_agent/domain/frequency_policy.py`.
- **Never assume RX is legal everywhere.** TETRA reception is
  ambiguous in some EU jurisdictions; paging reception is legal in
  most but not all countries.
- **Never redistribute intercepted personal messages** (POCSAG pages,
  AX.25 packets addressed to specific callsigns).
- **Do not spoof safety-of-life systems.** GPS, ADS-B, aviation
  voice, marine distress — all felonies in most jurisdictions.

## Related resources

- `docs/ctf_playbook.md` — first-60-seconds triage recipes
- `docs/rf_cheatsheet.md` — band-at-a-glance + modulation table
- `docs/safety.md` — full safety rationale
- `knowledge/MANIFEST.md` — corpus roadmap
