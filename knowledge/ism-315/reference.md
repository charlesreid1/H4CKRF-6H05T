# ism-315/reference.md — North American 315 MHz ISM

North American Part 15 §15.231 keyfob / TPMS / garage band. Overlaps
the amateur 1.25 m band by nature but keyfob/TPMS traffic sits inside
the specific 310–320 MHz window.

## Band boundaries

| Property | Value |
|---|---|
| Regulatory frame | FCC 47 CFR §15.231 (periodic transmitters) |
| Nominal band | 310–320 MHz (RiskAssessor's ISM allocation) |
| Center of activity | 315.000 MHz |
| Max field strength (§15.231) | 12,500 μV/m at 3 m at 315 MHz (~7 nW EIRP) |
| Duty cycle rules | Manual/keyfob-style bursts only |
| Region | US, Canada, most of the Americas |

Cross-record: `records/bands.json:band-ism-315`.

## Denizens

- **Automobile keyfobs (NA).** Most US market keyfobs sit in the 314.9
  or 315.0 MHz sub-window. Rolling code from most modern vehicles;
  fixed code on some early-2000s and older domestic vehicles.
- **TPMS (Tire Pressure Monitoring Systems).** NHTSA-mandated on all
  US passenger vehicles since 2007. Per-wheel transmitters. Schrader,
  Continental, Pacific/Cub, and Beru are the dominant chipset
  vendors.
- **Garage doors (older NA).** Fixed-code openers up to ~2010; rolling
  code (Chamberlain Security+, Genie Intellicode) dominant after.
- **Some doorbells and remote thermometers.** Less common than at
  433 MHz.

## Typical PHY

- **Modulation:** OOK (most keyfobs, TPMS, garage doors) or 2FSK
  (some higher-security keyfobs).
- **Symbol encoding:** Manchester at 2–4 kbps is the dominant PHY for
  keyfobs. PWM and PPM are also common in older systems.
- **Burst length:** 30–100 ms typical. Multiple bursts per press with
  ~20 ms gaps.
- **Preamble:** 8–24 bits of `1010...` or a fixed sync word (rare in
  §15.231 devices — the receiver usually just matches on the burst
  start).

## Capture recipe

```
sweep_spectrum(start_freq_hz=310_000_000,
               end_freq_hz=320_000_000,
               dwell_s=0.5)
# Look for a narrow OOK-shaped burst near 314.9-315.05.

capture_iq(target_freq_hz=315_000_000,
           sample_rate_hz=2_000_000,
           duration_s=5.0,
           lna_gain_db=24,
           vga_gain_db=30)

analyze_iq_modulation(iq_path)
# Should return OOK on top.

analyze_iq_symbols(iq_path, sample_rate_hz=2_000_000)
# Expect ~2000-4000 Hz for keyfob/TPMS traffic.

decode_manchester(iq_path, sample_rate_hz=2_000_000,
                  symbol_rate_hz=2048.0)
# Or decode_pwm if the pulse widths look distinct.
```

## Regulatory notes

- **TX with a HackRF in this band is a compliance question.** §15.231
  limits field strength to well below what the HackRF's TX chain
  produces at any gain. Replay experiments should use a dummy load or
  a shielded chamber.
- **Not BLOCKED** in the RiskAssessor — the gate permits it because
  it's ISM. Compliance is the operator's responsibility.

## Cross-references

- `knowledge/keyfobs/` — the attack model for fixed vs rolling code
- `knowledge/tpm/` — TPMS protocol details
- `knowledge/garage-doors/` — Genie / Chamberlain generations
- `knowledge/ism-433/` — the EU counterpart
