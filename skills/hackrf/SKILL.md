---
name: hackrf
description: Use whenever an operator's question or request touches RF, IQ, HackRF, a specific frequency, a modulation family, keyfobs, paging (POCSAG/FLEX), ADS-B, or any signal on the air. Backed by the `hackrf-agent-mcp` server — one safety-gated tool, `execute_command`, that funnels every RF action through a deterministic risk/approval/audit chain.
---

# HackRF co-pilot SKILL

## When to reach for this MCP

If the operator's question or request touches any of these, this MCP is the
tool:

- A specific frequency or band ("what's on 433.92?", "sweep 900-930 MHz")
- Modulation theory (OOK vs FSK, what QPSK looks like)
- Keyfobs, TPMS, garage doors, weather stations
- Paging (POCSAG/FLEX), ADS-B (RX-only), AIS
- A captured `.iq` file the operator wants analyzed or decoded
- Any transmit action on the HackRF

Do not attempt to reason about RF signals from model weights when the MCP
can answer from the corpus. If a `knowledge_lookup_*` verb exists for the
question, prefer it over free-form recall.

## How the funnel works

There is one tool: `execute_command`. It is discriminated by `action`.

- Knowledge actions (`knowledge_list_topics`, `knowledge_read`,
  `knowledge_search`, `knowledge_lookup_band`, …) are hardcoded `LOW` risk
  and run immediately. They read files on disk. They cannot cause RF
  emission and cannot touch libhackrf.
- Analysis actions (`read_iq_summary`, `decode_ook`, and the planned
  `analyze_iq_*` / `decode_*` verbs) operate on already-captured `.iq`
  files on disk. Also `LOW` risk. Also cannot touch libhackrf.
- Action actions (`sweep_spectrum`, `capture_iq`, `transmit_iq`, …) go
  through `RiskAssessor` → optional `PermissionService.check` → optional
  `ApprovalPort.request`. TX in a BLOCKED band is refused deterministically.

Read `docs/safety.md` before recommending TX. Never propose that the
operator "just try it" on a blocked band — the gate will refuse and it is
correct to refuse.

## Corpus depth cues

Every `knowledge/<topic>/` typically ships:

- `README.md` — orient
- `reference.md` — numbers
- `walkthrough.md` — worked examples
- `recognition.md` — how to spot this in a waterfall

Prefer `walkthrough.md` when the operator is doing rather than reading.
Prefer `recognition.md` when the operator has a spectrogram or capture and
is asking "what is this?"

Numeric claims should route through `knowledge_lookup_band`,
`knowledge_lookup_modulation`, `knowledge_lookup_protocol`, and the shared
`knowledge_verify_claim` sanity check. Free-form `knowledge_search` is a
last resort.

## Playbook — you've been handed a mystery frequency

1. Look up the band with `knowledge_lookup_band(freq_hz=…)`. If it comes
   back with `blocked_tx=true`, plan for RX-only from the start.
2. Sweep with `sweep_spectrum`. Match the occupancy pattern against
   `docs/ctf_playbook.md`.
3. Capture with `capture_iq`. Use `target_freq_hz`, not
   `center_freq_hz`, so the DC spike lands off your signal.
4. Analyze: `read_iq_summary` → `analyze_iq_modulation` →
   `analyze_iq_symbols` → the right `decode_*` verb.
5. Verify decoded frames with `knowledge_lookup_protocol` before claiming
   "this is POCSAG at 1200 baud" or "this is a Keeloq rolling code."

## The funnel invariant

You never see libhackrf. Every RF action is `execute_command`. Trying to
bypass the gate is a bug in reasoning, not a bug in the gate. If a
capability seems missing, the fix is to propose a new `CommandAction`
value with a deterministic risk classification — never a second tool that
reaches around the funnel.
