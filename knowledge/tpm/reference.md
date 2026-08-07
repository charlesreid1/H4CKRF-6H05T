# tpm/reference.md — Tire Pressure Monitoring Systems

Per-wheel radio sensors mandated on all US passenger vehicles since
2007. Each wheel has a battery-powered transmitter reporting pressure,
temperature, and (sometimes) rotation speed.

## Chipset vendors

- **Schrader** (largest global share, ~50%). NA + EU.
- **Continental** (VDO/Siemens). Broad OEM adoption.
- **Pacific Industrial** (Cub, PMV series). NA + Asian markets.
- **Beru**. Mostly EU.
- **Alligator** (universal aftermarket).

## Bands

- **NA vehicles:** 315.0 MHz (Part 15 §15.231).
- **EU vehicles:** 433.92 MHz (ETSI EN 300 220).
- **Some Asian markets:** 433 MHz or 315 MHz depending on region.

## Typical PHY

- **Modulation:** OOK for older sensors; some newer designs use
  FSK/GFSK.
- **Symbol encoding:** Manchester or PWM at 2-10 kbps depending on
  vendor.
- **Burst length:** ~10-50 ms per transmission.
- **Repetition rate:** Every ~90 seconds at highway speed; more
  frequent on pressure change; very quiet when stationary.

## Payload

A typical TPMS packet carries:

- **32-bit sensor ID** (unique per wheel, factory-programmed).
- **Pressure** (8 bits, PSI or kPa).
- **Temperature** (8 bits, °F or °C).
- **Battery status** (1 bit).
- **Rotation status / accel flag** (1 bit).
- **CRC** (8 or 16 bits, vendor-specific polynomial).

## Attack surface

TPMS has been repeatedly shown to be a privacy issue rather than a
safety issue:

- **ID broadcast every ~90 seconds** → a stationary receiver can
  fingerprint passing vehicles by TPMS ID.
- **No encryption in any current-generation sensor.**
- **Spoofing pressures** (Ishtiaq et al., 2010) can trigger dashboard
  warnings but not brake failure.
- **Bulk-scale surveillance** is the real concern — a network of
  TPMS receivers along highways builds vehicle-tracking data.

## Capture recipe

```
# Drive past the target OR pump the tire to trigger a transmission.
capture_iq(target_freq_hz=315_000_000,
           sample_rate_hz=2_000_000,
           duration_s=180.0)         # long window to catch a burst

decode_manchester(iq_path, sample_rate_hz=2_000_000, symbol_rate_hz=4800)
# Or try decode_pwm(short_us=250, long_us=500) for Schrader.
```

## Legality

- **RX only** — decoding your own or someone else's TPMS is
  generally permissible in the US and EU.
- **TX** — TX at 315 MHz is theoretically §15.231-allowed but the
  HackRF's output exceeds the field-strength cap. Bench-test with
  a dummy load or shielded chamber only.
- **Spoofing a vehicle's TPMS** to trigger a low-pressure warning is
  a nuisance-level offense in most jurisdictions.
- **The RiskAssessor does not BLOCK TPMS bands.** Compliance is the
  operator's responsibility.

## Cross-references

- `knowledge/ism-315/` — NA TPMS band
- `knowledge/ism-433/` — EU TPMS band
- `knowledge/keyfobs/` — similar attack surface, same PHY
