# crypto-in-rf — reference

Not every "encrypted" RF protocol is meaningfully encrypted. This is
the H4CKRF reference for what's in the wild, what's been broken, and
what still resists analysis.

## Keeloq — proprietary NLFSR

- **What it is.** A 64-bit block cipher built from a non-linear
  feedback shift register (NLFSR). 528 rounds. Used in Chamberlain,
  HCS, and many older keyfobs at 315/433 MHz.
- **Status.** Broken. Bogdanov (2007) published a slide-attack
  key-recovery in 2¹⁶ chosen plaintexts. Eisenbarth et al. (2008)
  extracted the manufacturer key from a fielded receiver by power
  analysis.
- **Effect for CTF.** Keeloq itself is defeated in principle, but
  most rolling-code implementations desync after a few button
  presses of stored replay — the counter matters more than the
  crypto. RollJam-style attacks (jam + replay) still work against
  many deployed systems.
- **H4CKRF verdict.** `records/crypto_in_rf.json → keeloq` is
  `confidence: primary`, broken academically, still deployed.

## HITAG2 — 48-bit stream cipher

- **What it is.** Immobilizer-and-keyfob cipher used by VW, PSA,
  Renault, and others in the early 2000s. 48-bit key, LFSR-based.
- **Status.** Broken. Verdult et al. (USENIX 2012) demonstrated a
  practical time-memory-tradeoff attack. Key recovery in
  minutes-to-hours on commodity hardware.
- **Effect for CTF.** If you see HITAG2 in a challenge, it's a
  puzzle about the *attack surface* (replay, weak counter, or the
  known cipher weakness), not a "guess the key" brute force.

## Passive Keyless Entry (PKE)

Not a cipher — a protocol family. The car challenges the fob (125 kHz
LF wakeup + 433 MHz UHF response). Attacks target *the relay*:

- **Relay attack.** Long-range NFC/RF bridge between the fob-in-house
  and the car-on-driveway. No cryptanalysis; the fob just answers
  faithfully to a challenge that came from a hijacked link.
- **Countermeasures.** UWB distance-bounding (Tesla Model 3 2023+,
  BMW 2020+). Motion-sleep on the fob (idle for N minutes → fob
  refuses to answer).

## GSM A5/1 and A5/2

- **A5/1.** 64-bit stream cipher over the GSM voice/data downlink.
  Real-time attacks demonstrated with GPU rainbow tables. Broken.
- **A5/2.** Export-crippled variant. Trivially broken (matter of
  seconds on a laptop) since 2003. Removed from GSM standards in
  2007 but some legacy handsets negotiate it.
- **A5/3 (KASUMI).** 128-bit; used in 3G. Better, but not
  post-quantum secure.

The H4CKRF role is *listening*, not attacking. Cellular downlink is
BLOCKED for TX regardless.

## TETRA TEA1-4

- **TEA1.** 80-bit key with only 32 bits of effective entropy —
  intentional backdoor. Broken by Midnight Blue in 2023.
- **TEA2, TEA3, TEA4.** Meant to be strong. Not confirmed broken as
  of the corpus era (2026).
- **TEA5, TEA6, TEA7.** Even newer; classified.

## P25 — DES-56 and AES-256

- **DES-56.** The original P25 encryption. 56-bit key, unenforced
  against modern hardware. Practical to key-search in hours.
- **AES-256.** The modern P25 standard. No known cryptographic
  weakness; attacks (if any) go through key management or
  side-channels.

## DMR — no encryption by default

Amateur DMR is unencrypted; commercial DMR uses ARC4 with a per-vendor
40-bit key. ARC4 is weak but the 40-bit key is what actually falls to
brute force.

## LoRa AppKey (LoRaWAN)

AES-128 in CMAC mode for MIC, AES-128 in ECB for payload encryption.
Not broken cryptographically. Attacks target the join procedure and
device-key extraction from cheap end nodes.

## When to say "not broken"

Cryptographic primitives can be strong even when the deployment is
weak. When evaluating a claim:

- **Practical attack demonstrated in academia + code released** →
  say "broken."
- **Theoretical attack, no released code** → say "reduced strength."
- **Weak keys or weak protocol** but strong primitive → say "the
  protocol is weak; the cipher is not."
- **Unknown / classified** → `unverified`.

## The trap catalog

- **"Rolling code defeats replay."** Needs qualification. Rolling
  code with a counter defeats simple replay; RollJam (jam + capture +
  replay-later) still works against many receivers.
- **"HITAG2 is impossible to crack."** False. Documented USENIX
  attack.
- **"AES cannot be broken."** Needs qualification. AES-128 has no
  cryptanalytic break; the key can still be leaked via side-channels
  or key-management flaws.

## Cross-references

- `knowledge/keyfobs/` — where Keeloq and HITAG2 live in practice
- `records/crypto_in_rf.json` — the machine-readable version
- `records/keyfobs.json` — per-vendor deployment status
- `knowledge/dmr/`, `tetra/`, `p25/` — trunking protocols
