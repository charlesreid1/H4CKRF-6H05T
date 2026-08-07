# ask-ook/reference.md — amplitude keying

## ASK-N

Amplitude-shift keying with N levels. `s(t) = a_k · cos(2π fc t)` where
`a_k ∈ {A_0, A_1, ..., A_{N-1}}`. Bandwidth ~= `(1 + α) · Rs` for
RRC-shaped, ~= `1.2 · Rs` for rectangular pulses.

## OOK — ASK with N=2, 100% depth

The two levels are `{0, A}`. `s(t) = b_k · cos(2π fc t)` where
`b_k ∈ {0, 1}`. When `b_k=0`, the carrier is *off*. This is the family
name used for 315/433 MHz keyfobs and most cheap ISM-band devices.

### Numeric properties

- **Bandwidth:** `~1.2 · Rs` for rectangular pulse; sidelobes rich in
  odd harmonics of the symbol rate.
- **Symbol rates in the wild:** 1000-4000 bps typical (keyfobs, weather
  stations); some 315/433 MHz TPMS bursts hit 9600 bps.
- **Duty cycle:** highly variable (Manchester on top → ~50% average
  on-time; PWM → 25-75% depending on bit; NRZ with long 1-runs →
  near 100%).

### Symbol-encoding layer on top

Almost never raw NRZ — usually Manchester or PWM to embed a clock:

- **Manchester over OOK:** the majority of keyfob PHYs. Two half-symbols
  per bit; a transition mid-bit distinguishes 0 from 1.
- **PWM over OOK:** many Chamberlain garage-door legacy remotes, older
  Chinese 433 MHz remotes.
- **PPM over OOK:** Acurite 592, Oregon Scientific V2 weather families.

### Framing

Typical frame: `preamble (0xAA 0xAA ...) + sync word (vendor-specific,
often 8-16 bits) + address (fixed per device) + payload + CRC-8/16`.
`rtl_433` catalogs ~250 device-specific variants.

### Regulatory

- **US 315 MHz:** FCC Part 15 §15.231. Periodic operation; strict field
  strength limits; keyfobs and garage doors are OK.
- **EU 433 MHz:** ETSI EN 300 220. 10 mW ERP cap, 10% duty cycle
  general limit.
- **US 902-928 MHz:** FCC Part 15 §15.247 (spread) / §15.249 (narrow).

## Citations

- Proakis & Salehi ch. 5, §5.2 — ASK theory.
- rtl_433 device catalog.
- Kamkar 2015 (RollJam disclosure) for OOK keyfob attack model.
