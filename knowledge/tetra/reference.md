# tetra/reference.md — Terrestrial Trunked Radio

ETSI standard. European public-safety digital voice trunking.
Dominant in EU/APAC/ME; almost absent in NA. Historically thought
"secure" until the TETRA:BURST research (Meijer/Wetzels et al., 2023)
disclosed cryptographic backdoors in TEA1/2/3/4.

## PHY

- **Modulation:** π/4-DQPSK (differential-encoded QPSK, π/4 offset).
- **Symbol rate:** 18 000 sym/s (18 kbaud).
- **Effective bit rate:** 36 kbps (2 bits/symbol).
- **Channel spacing:** 25 kHz.
- **Four-slot TDMA:** 56.67 ms superframe with 14 ms per slot.

## Framing

- **Multiframes** of 18 frames of 4 slots each.
- **Voice:** ACELP at 4.567 kbps per slot + FEC.
- **Signalling** on dedicated logical channels.

## Encryption

TEA1 through TEA7. TEA1 is deliberately weak (48-bit effective key
despite 80-bit key size — the TETRA:BURST disclosure). TEA2/3 stronger
but restricted-export. TEA4/5/6/7 newer, less-analyzed.

**Even where crypto is deployed correctly**, sniffing PHY is trivial;
decrypting requires the network key.

## Common bands

- **380–430 MHz** (UK, most of EU public safety).
- **410–430 MHz** (police / fire in some countries).
- **806–869 MHz** (US in a few cases; ATC in some regions).

## Legality

- **RX only, always.** TETRA is licensed public-safety spectrum
  wherever it's deployed. Decoding is legally ambiguous in most
  jurisdictions (some countries prosecute even reception; most
  tolerate it for research).
- **The RiskAssessor does not BLOCK TETRA-specific bands** — they
  vary by region. Operators must respect local law.

## What this MCP can and cannot decode

- **Can:** Recognize π/4-DQPSK on the waterfall via
  `analyze_iq_modulation`. Estimate symbol rate.
- **Cannot:** Voice decoding (ACELP is proprietary). Cannot decrypt
  TEA-encoded traffic.

## Cross-references

- `knowledge/dmr/`, `knowledge/p25/` — sibling systems
- `records/protocols.json:protocol-tetra`
- TETRA:BURST disclosure (Midnight Blue, 2023)
