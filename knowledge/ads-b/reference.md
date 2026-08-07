# ads-b/reference.md — Mode S / ADS-B at 1090 MHz

Aviation transponder replies + ADS-B extended squitter. Every
commercial aircraft in the world's controlled airspace broadcasts on
this frequency multiple times per second.

## Band boundaries

| Property | Value |
|---|---|
| Center frequency | 1090.000 MHz |
| Regulatory frame | 47 CFR §87.131 (aviation safety-of-life) |
| RiskAssessor state | **BLOCKED for TX** (1087–1093 MHz) |
| Region | Universal (ICAO) |
| Modulation | PPM at 1 Mbps |
| Chip width | 0.5 μs |
| Long-frame length | 112 bits (14 bytes) |
| Short-frame length | 56 bits (7 bytes) |

Cross-record: `records/bands.json:band-ads-b`.

## Why this is BLOCKED for TX

1090 MHz is aviation safety-of-life. Any transmission on this
frequency could interfere with real air-traffic-control interrogations
and ADS-B position reports. The RiskAssessor's BLOCKED table refuses
TX in 1087–1093 MHz regardless of any grant.

**Decoding IS legal and welcome.** Millions of hobbyists run
`dump1090` and feed FlightAware, ADS-B Exchange, etc.

## Signal structure

Every Mode S message consists of:

1. **Preamble.** 8 μs at 1 Mbps chip rate = 16 chips. Pulse pattern:
   pulses at 0.0, 1.0, 3.5, 4.5 μs (each 0.5 μs wide).
2. **Data.** 112 bits (long) or 56 bits (short), PPM-encoded at
   1 Mbps: bit=1 = pulse in first half of the 1 μs slot, bit=0 =
   pulse in second half.

The `decode_ads_b` verb requires `sample_rate_hz >= 2 MHz` to
resolve the 0.5 μs chip width.

## Frame taxonomy

The **DF (downlink format)** field is the first 5 bits.

| DF | Length | Purpose |
|---|---|---|
| 0 | 56 | Short air-air surveillance (TCAS reply) |
| 4 | 56 | Surveillance altitude reply |
| 5 | 56 | Surveillance identity reply |
| 11 | 56 | All-call reply |
| 16 | 112 | Long air-air surveillance |
| 17 | 112 | **Extended squitter (ADS-B)** — position/velocity |
| 18 | 112 | Extended squitter, non-transponder |
| 19 | 112 | Military extended squitter |
| 20 | 112 | Comm-B altitude reply |
| 21 | 112 | Comm-B identity reply |
| 24 | 112 | Comm-D |

DF17 is what "ADS-B" usually refers to. For DF17 the 112-bit CRC-24
should be zero. For DF11 the CRC equals the ICAO24 address.

## CRC-24

Generator polynomial `0xFFF409` (the "Mode S CRC"). For a valid
DF17 frame the CRC over all 112 bits (including the trailing 24-bit
FCS) is zero. `decode_ads_b` returns `crc_ok=True` in that case.

## ICAO24

The 24-bit airframe address (bits 8–31 of the message). Uniquely
identifies the aircraft. Public databases (FlightAware, opensky) map
ICAO24 → registration → owner.

## Capture recipe

```
sweep_spectrum(start_freq_hz=1_089_000_000,
               end_freq_hz=1_091_000_000,
               dwell_s=0.5)
# Should see busy short bursts at exactly 1090.0.

capture_iq(target_freq_hz=1_090_000_000,
           sample_rate_hz=2_000_000,
           duration_s=30.0,
           lna_gain_db=32,
           vga_gain_db=30)

decode_ads_b(iq_path, sample_rate_hz=2_000_000, max_frames=64)
```

## Antennas

- **1090 MHz is a good match for a 6.5 cm quarter-wave whip.**
- **Higher gain helps a lot.** Even a $5 collinear roof-mount pulls in
  aircraft 100+ km away.
- **A commercial pre-filtered LNA (SAW filter + LNA)** is a common
  upgrade — knocks down out-of-band interference from cellular.

## Cross-references

- `knowledge/regulatory/` — why 1090 MHz is BLOCKED for TX
- `knowledge/modulation/` — PPM basics
- `records/protocols.json:protocol-mode-s-ads-b` — the machine-readable
  version
