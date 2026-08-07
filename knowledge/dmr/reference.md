# dmr/reference.md — Digital Mobile Radio

ETSI standard (TS 102 361) for two-way land-mobile radio. Very
widely deployed for commercial fleet dispatch, hunting/hiking clubs
(via hotspots), and amateur networks (BrandMeister, DMR-MARC).

## PHY

- **Modulation:** 4FSK, ±1.944 kHz outer deviation.
- **Symbol rate:** 4800 sym/s.
- **Effective bit rate:** 9600 bps (2 bits/symbol).
- **Channel spacing:** 12.5 kHz.
- **Two-slot TDMA:** 60 ms superframe with 30 ms per slot. Doubles
  effective capacity vs FDMA.

## Framing

- **Sync patterns:** Per-slot, per-direction (BS-in/MS-in), various.
- **Voice frame:** AMBE+2 vocoder at 3600 bps per slot + FEC.
- **Data frame:** MAC-level data with retransmission.

## Common bands

- **VHF:** 136–174 MHz.
- **UHF:** 400–470 MHz.
- **800/900 MHz:** Public safety and some commercial.

## Legality

- **RX only unless licensed.** DMR is licensed spectrum in every
  region. Amateur DMR requires a Part 97 license and specific
  amateur repeaters (BrandMeister TG9990 for testing, etc.).
- **The RiskAssessor does not BLOCK DMR bands** — most DMR sits in
  land-mobile allocations that are not in the BLOCKED list.
  Operators must respect their license.

## What this MCP can and cannot decode

- **Can:** Recognize 4FSK on the waterfall. Estimate symbol rate
  (~4800). Confirm channel spacing.
- **Cannot:** Voice decoding (AMBE+2 is proprietary; DSD/DSD+ can
  handle it externally). Data decoding requires a full stack.

For DMR reception, use `dsd-fme` or `SDRTrunk` externally.

## Cross-references

- `knowledge/tetra/`, `knowledge/p25/` — sibling digital-voice
  trunking systems
- `records/protocols.json:protocol-dmr`
