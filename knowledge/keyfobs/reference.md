# keyfobs/reference.md — automobile keyfob systems

The full attack model: what each generation transmits, how the
security evolved, and what an attacker can and cannot do.

## Generations (roughly chronological)

### Fixed code (~1990s)

- **PHY:** OOK at 315 or 433 MHz, Manchester or PWM at ~2 kbps.
- **Payload:** Static 24–40 bits per press. Every press transmits
  the identical bit pattern.
- **Vulnerability:** Trivial replay. Capture once, retransmit forever.
  Chamberlain Security+ 1.0, early Genie, early domestic automobiles.
- **Defense:** None. The industry moved to rolling code after mass
  fixed-code attacks in the early 2000s.

### Rolling code — Keeloq (Microchip HCS series, ~1996–present)

- **PHY:** OOK at 315 or 433 MHz, Manchester at 2–4 kbps.
- **Payload:** 32-bit encrypted counter + 28-bit vehicle serial + 4
  function bits. Counter increments with every press.
- **Crypto:** Keeloq NLFSR (non-linear feedback shift register), 64-bit
  key, 32-bit block. The counter is encrypted with the key; the
  receiver decrypts and compares against its expected next-counter
  value.
- **Vulnerability class:** Fresh replay defeated by counter. RollJam
  (Samy Kamkar, 2015) captures + jams: attacker records press N and
  jams the receiver, so the counter never advances at the receiver.
  Attacker later replays press N.
- **Related:** HCS200/300/301/360/410/473 chips; identical protocol.

### KeeLoq HITAG2 (~2000–present, some Asian vehicles)

- **PHY:** 315/433 MHz OOK/2FSK.
- **Payload:** HITAG2 crypto, 48-bit key. Weaker than Keeloq in
  practice (published attacks recover keys in minutes with 1000-2000
  captured presses).
- **Vulnerability:** Timing side-channel attacks are the standard
  research (Verdult/Garcia et al.).

### Passive Keyless Entry (PKE) (~2007–present)

- **Different beast.** No fob press. LF (125 kHz) LFID → challenge
  from car → UHF (315/433) response from fob.
- **Vulnerability:** Relay attacks. Two attackers: one near the car
  (LF antenna), one near the owner's fob (UHF antenna). Together,
  they extend the "fob is nearby" signal to arbitrary distance.
- **Not solvable by RF-only tools.** Requires dedicated LF + UHF
  hardware.

### AES-CMAC rolling code (~2020s, high-end vehicles)

- **PHY:** 315/433 MHz FSK, some at 900 MHz.
- **Payload:** AES-128 rolling code with challenge-response
  authentication over a secondary UHF link.
- **Vulnerability:** No known practical replay. Cryptographic
  strength assumes proper key management (which some vendors get
  wrong — Kia, Ford recalls).

## Attack model summary

| Attack | Fixed code | Keeloq rolling | HITAG2 | PKE | AES |
|---|---|---|---|---|---|
| Fresh replay | ✔ | ✗ | ✗ | ✗ | ✗ |
| RollJam | ✔ | ✔ | ✔ | N/A | ✗ |
| Key recovery | N/A | Hard | Practical | N/A | Very hard |
| Relay | ✗ | ✗ | ✗ | ✔ | ✗ |
| Sniff → decrypt | ✔ | (needs key) | (few captures) | N/A | ✗ |

## Legality

- **Replay of a fob against a car you don't own is a felony in most
  jurisdictions** (unauthorized access, DMCA §1201 §f exemption
  varies).
- **Research on your own vehicle is generally legal** (§1201's
  security-research exception, if you comply with the notification
  requirements).
- **Never do live-fire testing on someone else's vehicle.**
- **The RiskAssessor does not BLOCK keyfob TX bands** (315/433 are
  ISM). Compliance is the operator's responsibility.

## What this MCP can do

- **RX + decode:** `capture_iq` on 315 or 433 MHz →
  `analyze_iq_modulation` → `decode_manchester` (or `decode_pwm`).
  Full bit stream extraction is expected.
- **Recognize fixed vs rolling:** compare multiple captures. Identical
  = fixed. Incrementing counter (see records/keyfobs.json) = rolling.
- **TX for replay:** yes, via `transmit_iq` with a grant. But — see
  legality.
- **Not supported:** Keeloq key recovery, HITAG2 cryptanalysis, PKE
  relay attacks. Out of scope for this MCP.

## Cross-references

- `records/keyfobs.json` — per-vendor catalog
- `knowledge/ism-315/` — NA keyfob band
- `knowledge/ism-433/` — EU keyfob band
- `knowledge/crypto-in-rf/` — Keeloq / HITAG2 crypto details
