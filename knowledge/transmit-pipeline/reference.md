# transmit-pipeline/reference.md — from IQ file to on-air

## The path

```
IQ file (.cs8)
   |
   |  transmit_iq({iq_path, freq_hz, tx_vga_db, sample_rate_hz})
   V
[ path validation ]                                    <- SessionPaths
   |
   V
[ grant coverage check ]                               <- PermissionService
   |
   V
[ RiskAssessor gate ]                                  <- freq_hz vs BLOCKED table
   |
   V
[ operator approval prompt ]                           <- unless grant pre-authorized
   |
   V
[ HackRF driver ]  -> hackrf_transfer -t
   |
   V
[ MAX5864 DAC ]  -> RF front end -> antenna
```

## Path validation

- `iq_path` MUST be under the session's canonical root
  (`SessionPaths.session_dir()`).
- Symlinks are followed once and re-validated.
- Reject: `..`, absolute paths outside the session root, symlinks
  pointing outside.

## Grant coverage

`PermissionService.covers_transmission(grant, freq_hz, tx_vga_db)`:

- Grant carries a **frequency range** and a **max TX VGA gain**.
- Coverage passes iff `freq_hz` is in the range AND `tx_vga_db` <=
  grant max.
- Grants are session-scoped and human-approved before issuance.

## RiskAssessor gate

- Hardcoded BLOCKED table. Not readable by the LLM.
- `regulatory.json` documents the same rules for reference only.
- Any freq in a BLOCKED band → `RiskAssessment: BLOCKED` → the pipeline
  refuses. No override at the LLM layer.

BLOCKED bands include (not exhaustive):

- Aviation voice (118-137 MHz).
- 1030 MHz interrogator, 1090 MHz Mode S reply.
- GPS L1 (1575.42 MHz), L2 (1227.60 MHz), L5 (1176.45 MHz).
- Marine distress channel 16 (156.800 MHz).
- Cellular downlink bands (Part 22/24/27).
- Emergency services (per-jurisdiction; conservative defaults).

## Amplitude scaling

- MAX5864 DAC is 8-bit signed → `[-128, +127]`.
- `hackrf_transfer -t` reads `.cs8` verbatim.
- Numpy generation should target `max(|iq|) ~= 0.9` before packing to
  `.cs8` — leaves ~1.5 dB of DAC headroom.

## TX VGA vs EIRP

Roughly:

- HackRF max TX power below 2 GHz: ~+10 dBm at 20 dB VGA.
- Above 2 GHz: ~+5 dBm at max VGA.
- Antenna gain (dBi) adds directly.
- **EIRP = TX_power + antenna_gain_dBi - feedline_loss**.

For §15.231 (315 MHz keyfob band) compliance the FCC limit is
60 dBμV/m at 3 m ≈ ~15 nW EIRP — the HackRF at max VGA easily
exceeds this. **Field-tests only in a screen room or on your own
gear.**

## Session capture-time budget

`MAX_CAPTURE_MINUTES` bounds cumulative capture+TX time per session
(see `docs/safety.md`). Once exhausted, `transmit_iq` refuses further
TX until session reset.
