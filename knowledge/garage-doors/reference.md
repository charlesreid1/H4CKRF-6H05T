# garage-doors/reference.md — garage-door opener generations

The residential garage-door opener market is roughly three vendors
(Chamberlain/LiftMaster, Genie, Sommer) each with their own security
generations. Below covers the ones a HackRF is likely to encounter.

## Chamberlain / LiftMaster / Craftsman (same parent)

### Security+ 1.0 (~1990s-2011)

- **PHY:** 315 MHz OOK, Manchester at 2 kbps.
- **Security:** 3-byte fixed code + 2-byte serial. Fixed replay
  works.
- **Vulnerable:** Yes.

### Security+ 2.0 (2011–present, ubiquitous)

- **PHY:** 310/315/390 MHz OOK, Manchester at 4 kbps.
- **Security:** Rolling code, proprietary NLFSR-style crypto (not
  Keeloq).
- **Vulnerable:** RollJam works in principle; live attacks published
  by Samy Kamkar.

## Genie Intellicode / Intellicode 2

- **PHY:** 315 MHz (NA) or 433 MHz (EU) OOK.
- **Security:** Rolling code, Keeloq-based.
- **Vulnerable:** Same as any Keeloq system.

## Genie (very old, "Excelerator" / mechanical DIP-switch)

- **PHY:** 300–390 MHz OOK, some 27 MHz older units.
- **Security:** DIP-switch code (fixed, 8-12 bit). Every unit ships
  with a mechanical selector that the owner sets to any pattern.
- **Vulnerable:** Absolutely. Only 256-4096 possible codes.

## Sommer (EU)

- **PHY:** 434.42 MHz FSK.
- **Security:** Encrypted rolling.
- **Vulnerable:** Some models had known key-recovery vulnerabilities
  circa 2015-2018.

## Attack summary

| Vendor / Gen | Vulnerable | Notes |
|---|---|---|
| Genie DIP-switch (~1970s-90s) | ✔ Very | 8-12 bit static code |
| Chamberlain Security+ 1.0 | ✔ | Fixed 3-byte payload |
| Chamberlain Security+ 2.0 | Partial | RollJam only |
| Genie Intellicode | Partial | Keeloq, same as keyfobs |
| Sommer | Partial | Some models |
| Modern rolling code (2020+) | Unknown |  |

## Capture recipe

```
sweep_spectrum(start_freq_hz=310_000_000,
               end_freq_hz=320_000_000,
               dwell_s=0.5)

capture_iq(target_freq_hz=315_000_000,
           sample_rate_hz=2_000_000,
           duration_s=10.0)

decode_manchester(iq_path, sample_rate_hz=2_000_000, symbol_rate_hz=4000)
```

## Cross-references

- `records/keyfobs.json` — Genie Intellicode, Chamberlain S+
  entries
- `knowledge/keyfobs/` — the broader attack model
- `knowledge/ism-315/` — NA opener band
- `knowledge/ism-433/` — EU opener band
