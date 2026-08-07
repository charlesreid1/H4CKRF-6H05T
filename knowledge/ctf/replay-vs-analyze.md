# replay-vs-analyze — which strategy fits

Given a captured signal you want to reproduce, when do you replay it
verbatim vs. when do you actually decode, understand, and re-encode?

## Replay wins when

- **Fixed-code system.** Every button press is identical bits. Replay
  the capture, unlock. Older garage doors, HomeEasy/Nexa 433 MHz,
  cheap RF relay boards.
- **The CTF asks for a proof-of-capability.** The flag is granted for
  demonstrating "I can retransmit this exactly" — bit-level fidelity
  is what matters, not understanding.
- **You have a grant covering the band + gain.** The H4CKRF funnel
  will refuse replay in a blocked band regardless.
- **Understanding the protocol is out of scope** for the time budget.

Practically: `capture_iq` → `transmit_iq` with the same `iq_path`.
The captured baseband will re-radiate through the same tuner
mechanics. Watch: gain settings must match, and the receiver's noise
floor might be different from yours.

## Analyze wins when

- **Rolling-code system.** Replay defeats itself the moment the
  legitimate fob presses again — the counter has moved on. RollJam
  works but is unreliable and often noticed. Decoding + counter
  advancement is more robust.
- **The flag is inside the decoded frame.** Text, hash, QR, or
  structured data hidden in a decoded packet body is only visible
  after decode.
- **The band prevents TX.** Every BLOCKED band prohibits replay by
  gate refusal. Analysis is the only viable path (ADS-B, GNSS,
  aviation voice, marine distress).
- **You need to generalize.** "Given this one signal, transmit a
  similar-but-different one" requires understanding the framing.

## When both work — pick analyze

The extra time you spend understanding the protocol pays off in
downstream challenges. A CTF that starts with a keyfob replay usually
ends with a rolling-code decode; skipping the analyze step early
means re-doing it under time pressure later.

## Decision tree

```
Is TX allowed in this band?
├─ No  → Analyze (RX-only workflow)
└─ Yes → Is the signal fixed-code?
         ├─ Yes → Replay is fine; note polarity + gain
         └─ No  → Is the flag in the frame body?
                  ├─ Yes → Analyze; the frame contents are the flag
                  └─ No  → Analyze; a rolling-code replay won't work
```

## Failure modes for replay

- **Gain mismatch.** TX at same gain as RX doesn't give the same
  received power — receiver's LNA is not calibrated the same way.
- **Timing drift.** HackRF's TCXO drifts a few ppm/°C; a long replay
  will slowly slide off the receiver's expected symbol timing.
- **Duty-cycle limit.** Some rolling-code receivers require a
  minimum inter-press gap. Replaying two captures back-to-back
  looks like a jamming attempt to the receiver.

## Failure modes for analyze

- **Wrong assumed encoding.** Manchester with the wrong polarity, or
  PWM misread as OOK, yields consistent-looking garbage. Always
  verify with a CRC or a sanity check on the decoded payload.
- **Frame boundary drift.** If you decode across a batch gap without
  aligning, half the codewords will be misassembled.

## Cross-references

- `unknown-keyfob.md` — the pre-decode triage
- `../crypto-in-rf/` — when a "rolling code" is actually encrypted
- `../keyfobs/` — the full attack model
