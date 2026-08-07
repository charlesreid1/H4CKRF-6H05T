# p25/reference.md — Project 25

TIA/EIA-102 standard. North American public-safety digital voice
trunking. Analog to TETRA in role.

## Two PHY variants

### P25 Phase 1

- **Modulation:** C4FM (compatible with FM receivers) or CQPSK
  (compatible with linear-envelope receivers). Same 4-level symbol
  space, different pulse-shaping.
- **Symbol rate:** 4800 sym/s.
- **Effective bit rate:** 9600 bps.
- **Channel spacing:** 12.5 kHz.
- **Access:** FDMA.

### P25 Phase 2

- **Modulation:** H-CPM (Harmonized Continuous Phase Modulation).
- **Symbol rate:** 6000 sym/s.
- **Access:** Two-slot TDMA — doubles capacity vs Phase 1.
- **Deployment:** Growing but not universal.

## Framing

- **Voice:** IMBE (Phase 1) or AMBE+2 (Phase 2) vocoder.
- **Trunking control channel** carries signaling on a dedicated
  frequency.

## Encryption

- **DES-OFB / AES-256 / ADP** are the standard cipher suites.
- **ADP (Automatic Digital Encryption, aka RC4-40)** was
  cryptographically broken circa 2011 — practical key recovery
  attacks exist.
- **DES** is weak but requires 2^56 offline work.
- **AES-256** is currently secure if the key management is correct.

## Common bands

- **VHF:** 136–174 MHz.
- **UHF:** 380–512 MHz.
- **700/800 MHz:** Federal FirstNet + public safety.

## Legality

- **RX only, always.** P25 is licensed public-safety spectrum.
- **The RiskAssessor BLOCKs 758–775 MHz** (FirstNet) and 851–854
  (NPSPAC) — those are hardcoded in `frequency_policy.py`. Other P25
  frequencies are not blocked but are still licensed spectrum;
  compliance is the operator's responsibility.

## What this MCP can and cannot decode

- **Can:** Recognize C4FM 4-level modulation. Estimate symbol rate.
- **Cannot:** Voice decoding. Use `DSD+` or `SDRTrunk` externally.

## Cross-references

- `knowledge/dmr/`, `knowledge/tetra/` — sibling systems
- `records/protocols.json:protocol-p25`
- `knowledge/regulatory/` — FirstNet BLOCKED band details
