# ism-433/reference.md — European 433 MHz ISM

The default answer to "just decode this waterfall." European SRD
sub-band, but the world's most popular hobbyist RF playground —
weather stations, keyfobs, wireless doorbells, garage openers, and
cheap Chinese IoT modules all live here regardless of region.

## Band boundaries

| Property | Value |
|---|---|
| Regulatory frame (EU) | ETSI EN 300 220 (Short Range Devices) |
| Regulatory frame (US) | 47 CFR Part 15 §15.231 for keyless entry |
| Nominal band | 433.050–434.790 MHz (Region 1 SRD) |
| Center of activity | 433.920 MHz |
| Duty cycle (EU) | 10% typical for keyfob-style, 0.1% for continuous |
| ERP limit (EU) | 10 mW (§8.5 dBm EIRP) |
| Amateur overlap (US) | Yes — 420–450 MHz is 70 cm amateur (secondary) |
| Region | EU primary; also used in NA/APAC by hobby devices |

Cross-record: `records/bands.json:band-ism-433`.

## Denizens

- **Weather stations.** Acurite, Fine Offset, La Crosse, Oregon
  Scientific, Bresser. Each vendor has its own PHY; `rtl_433` is the
  reference decoder catalog for ~200 sub-protocols.
- **Automobile keyfobs (EU).** Fixed and rolling code. Some
  cross-market vehicles use 433 in EU, 315 in NA.
- **Garage doors (EU).** Nice, FAAC, Sommer. Similar generations to
  the NA vendors but at 433 MHz.
- **TPMS (EU).** Same chipsets as NA, but in the EU 433 SRD
  sub-band.
- **Cheap wireless doorbells and PIR sensors.** Aliexpress-tier
  modules.
- **Amateur experiments (US).** 70 cm APRS is here in some regions;
  low-power beacons; ad-hoc data links.

## Typical PHY

- **Modulation:** OOK is dominant (Manchester/PWM/PPM at 1–4 kbps).
  Some higher-security devices use GFSK.
- **Symbol encoding:** Manchester most common, PWM (short/long pulse
  widths) second, PPM (pulse position within a symbol slot) third.
- **Burst structure:** Preamble (10–20 ms of `1010...`) + sync word
  (fixed pattern) + payload + optional CRC.

## Capture recipe

```
sweep_spectrum(start_freq_hz=433_000_000,
               end_freq_hz=435_000_000,
               dwell_s=1.0)

capture_iq(target_freq_hz=433_920_000,
           sample_rate_hz=2_000_000,
           duration_s=10.0,
           lna_gain_db=24,
           vga_gain_db=32)

analyze_iq_modulation(iq_path)   # → OOK on top
analyze_iq_symbols(iq_path, sample_rate_hz=2_000_000)
                                   # → 1000-4000 typical
decode_manchester(iq_path, sample_rate_hz=2_000_000,
                  symbol_rate_hz=2048.0)
```

For weather stations specifically, `rtl_433`'s device-detection logic
outperforms a first-principles decoder — the corpus recommends
handing the capture to `rtl_433` after the initial ID.

## Regulatory notes

- **US operators must not TX freely here.** In the US, 433 MHz is
  amateur 70 cm — Part 97 privileges required. §15.231 keyfob-style
  use is legal but very low power.
- **EU operators may TX under §300 220** with the duty-cycle and ERP
  limits above.
- **Not BLOCKED** in `RiskAssessor`. Compliance stays the operator's
  responsibility.

## Cross-references

- `knowledge/weather-stations/` — vendor-by-vendor PHY notes
- `knowledge/keyfobs/` — attack model
- `knowledge/garage-doors/` — Genie/Chamberlain/Sommer
- `knowledge/tpm/` — TPMS PHY
- `knowledge/ism-315/` — the NA counterpart
