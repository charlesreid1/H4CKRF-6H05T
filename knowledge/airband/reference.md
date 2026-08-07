# airband/reference.md — Aviation VHF voice

The 118–137 MHz band carries air-traffic-control voice, ATIS
(Automatic Terminal Information Service), tower/ground/approach/CTAF,
and pilot-to-pilot chatter.

## Band boundaries

| Property | Value |
|---|---|
| Nominal band | 118.000–137.000 MHz |
| Regulatory frame | 47 CFR §87.171 (US); ICAO Annex 10 globally |
| Modulation | Analog AM (DSB) |
| Channel spacing (legacy) | 25 kHz |
| Channel spacing (modern EU) | 8.33 kHz |
| RiskAssessor state | **BLOCKED for TX** |
| Special frequency | 121.500 MHz international aeronautical emergency |
| Region | Universal (ICAO) |

Cross-record: `records/bands.json:band-airband`, `band-vhf-guard`.

## Why TX is BLOCKED

Aviation voice is safety-of-life spectrum. Any transmission on airband
frequencies could interfere with ATC operations. The RiskAssessor's
BLOCKED table refuses TX in 118–137 MHz regardless of any grant.

**Decoding IS legal** in most jurisdictions and welcome for hobbyists
(pilotedge, LiveATC, etc. run scanners for public consumption).

## PHY

- **Analog AM DSB (double sideband with carrier).** Envelope
  detection recovers the audio.
- **Audio bandwidth:** ~3 kHz nominal; some voice quality up to 5 kHz.
- **Channel occupied bandwidth:** ~6 kHz (2 × audio BW).

## Common frequencies

- **121.500 MHz** — International aeronautical emergency (VHF Guard).
  ELT (Emergency Locator Transmitter) sweeping-tone signals on this
  frequency.
- **123.000 MHz** — Air-air Multicom (private airfields, some hot-air
  balloon and helicopter operations).
- **123.100 MHz** — Search and rescue.
- **131.550 MHz** — ACARS (aircraft-to-airline data — see
  `knowledge/satellite/`).
- **136.975 MHz** — VDL Mode 2 data (VHF Data Link).
- **Regional tower/ground/approach frequencies** vary by airport;
  published in airport charts (AIP / TAF).

## Capture recipe

```
sweep_spectrum(start_freq_hz=118_000_000, end_freq_hz=137_000_000,
               dwell_s=1.0)
# In a busy metro area, you'll see many narrow AM channels.

capture_iq(target_freq_hz=124_275_000,   # a specific tower channel
           sample_rate_hz=200_000,
           duration_s=60.0)

# AM demod happens externally — this MCP does not currently ship an
# AM voice demod verb. Feed the .iq to gqrx or a Python AM script.
```

## What this MCP can and cannot decode

- **Can:** Sweep, identify channel activity, capture the raw IQ.
  For manual AM demod from a capture, use `analyze_iq_modulation`
  to confirm the family, then work with `hw.dsp.iq_to_envelope` +
  audio playback tools of choice.
- **Cannot:** ACARS message decoding (custom MSK protocol; use
  `acarsdec` externally).

## Cross-references

- `knowledge/regulatory/` — the FCC Part 87 details
- `records/bands.json:band-airband` — machine-readable
- `knowledge/marine-vhf-ais/` — sibling voice band, similar rules
