# marine-vhf-ais/reference.md — Marine VHF and AIS

156–162 MHz marine VHF band. Voice channels, DSC signaling, and AIS
(Automatic Identification System) for ship tracking.

## Band boundaries

| Property | Value |
|---|---|
| Nominal band | 156.025–162.025 MHz |
| Regulatory frame | 47 CFR Part 80 (US); ITU RR globally |
| Voice modulation | FM narrowband (5 kHz deviation) |
| Channel spacing | 25 kHz |
| Distress channel | 156.800 MHz (Channel 16) — **BLOCKED for TX** |
| DSC channel | 156.525 MHz (Channel 70) |
| AIS channel A | 161.975 MHz |
| AIS channel B | 162.025 MHz |
| Region | Universal (ITU) |

Cross-records: `records/bands.json:band-marine-distress` (156.8),
plus AIS channels (not currently in BLOCKED list — RX-encouraged).

## Why part of this is BLOCKED

The RiskAssessor BLOCKs 156.7625–156.8375 MHz — the distress and DSC
sub-band. TX outside those specific frequencies (on regular marine
voice channels) is not BLOCKED by the gate but is licensed spectrum;
compliance is the operator's responsibility.

## Voice channels

- **Channel 16 (156.800):** International distress and calling.
  BLOCKED for TX. Anyone in trouble on the water uses this.
- **Channel 6 (156.300):** Intership safety.
- **Channel 9 (156.450):** Boater calling (US commercial).
- **Channel 13 (156.650):** Bridge-to-bridge safety.
- **Channel 22A (157.100):** USCG working (US).

Full US channel list in 47 CFR §80.371.

## AIS (Automatic Identification System)

Every ship above 300 GT (SOLAS regulation) plus most commercial and
many recreational vessels broadcasts position via AIS.

- **PHY:** GMSK, 9600 bps, BT product 0.4.
- **Access:** Self-organizing TDMA (SO-TDMA) — 2250 slots per minute
  per channel.
- **Two channels alternated:** 161.975 (A) and 162.025 (B).
- **Message types:** 27 defined. Type 1/2/3 are position reports;
  type 5 is voyage-related; type 21 is aids-to-navigation; type 24 is
  static/voyage data (extended).
- **Payload:** Encoded in 6-bit "ASCII-armored" ITU form. MMSI,
  latitude, longitude, speed, course, IMO number, ship name.

## Capture recipe (AIS)

```
capture_iq(target_freq_hz=162_000_000,   # covers both A and B
           sample_rate_hz=250_000,
           duration_s=60.0,
           lna_gain_db=32,
           vga_gain_db=30)

# Currently this MCP does not have a native AIS decoder. Use
# aisdecoder or rtl-ais externally, or convert the .iq to
# 48 kHz mono audio and pipe to gnuais.
```

## What this MCP can and cannot decode

- **Can:** Sweep, capture, recognize GMSK modulation
  (`analyze_iq_modulation` will surface constant-envelope; the caller
  correlates with band knowledge).
- **Cannot yet:** Full AIS decoding. Requires GMSK demod +
  bit-stuffing + CRC-16 + 6-bit payload decode. Out of scope for now
  but a natural future addition.
- **Cannot:** Voice channel decoding — needs FM demod verb.

## CTF flag patterns

- **A specific MMSI IS the flag.** AIS payloads are cleartext;
  a specific ship's identifier encodes something.
- **Ship name IS the flag.** Some CTFs inject a fake AIS beacon.
- **The channel used IS the flag** — A vs B.

## Cross-references

- `knowledge/regulatory/` — 47 CFR Part 80
- `knowledge/modulation/` — GMSK primer
- `records/bands.json:band-marine-distress`
