# ads-b-recon — an aircraft's squawk is the flag (RX only)

ADS-B challenges are RX-only. The HackRF **never** transmits on 1090
MHz — the gate refuses and it is correct to refuse. Every ADS-B CTF
puzzle is about reading, not writing.

## The signature

- **Band.** 1090 MHz (Mode S extended squitter).
- **Modulation.** PPM at 1 μs per bit; 112-bit frames.
- **Symbol rate.** 1 Msps chip rate → capture at `sample_rate_hz >=
  2_000_000`.

## The workflow

1. **Capture** with `target_freq_hz=1_090_000_000`,
   `sample_rate_hz=2_000_000`, `duration_s=5-30`. Longer captures
   catch more aircraft.
2. **Decode** with `decode_ads_b`:

```jsonc
decode_ads_b({iq_path, sample_rate_hz: 2_000_000, max_frames: 128})
// -> {"frames": [{"df": 17, "icao24_hex": "abcdef", "raw_hex": "...", "crc_ok": true}]}
```

3. **Look at the ICAO24 addresses.** Every aircraft has a unique
   24-bit ICAO address. Cross-reference with a public registry
   (opensky, dump1090, adsbexchange).

## Common CTF patterns

- **Flag is a callsign.** Frame type DF=17 with subtype "Aircraft
  Identification" (BDS 0,8) contains the 8-character callsign.
- **Flag is a tail number.** Static per-aircraft; look up ICAO24 in a
  registry.
- **Flag is a squawk.** The transponder squawk code (4-digit octal)
  from ADS-B "Aircraft status" frames.
- **Flag is a position.** Lat/lon in the frame decodes to a
  location; the CTF wants the lat/lon rounded to a nearby landmark.

## Trap catalog

- **"You can transmit ADS-B to test."** False. Cat-A safety-of-life
  band; TX BLOCKED. Even legitimate ADS-B-Out is licensed.
- **"Every DF=17 frame has a callsign."** False. Frame content
  depends on the subtype/BDS code.
- **"Callsigns are unique per flight."** True for a given flight
  leg; the aircraft's ICAO24 stays the same for the airframe's life.

## Failure modes

- **`crc_ok=false` on every frame.** CRC-24 with polynomial
  0xFFF409 is the standard. If it fails, check that
  `sample_rate_hz` is at least 2 Msps (the decoder needs 0.5 μs
  chip resolution).
- **No frames returned.** The antenna isn't near an airport. Move
  the antenna to a window; ADS-B is line-of-sight and needs a clear
  view of the sky.

## Cross-references

- `../ads-b/` — full protocol reference
- `../regulatory/` — why 1090 is BLOCKED for TX
- `packet-flag.md` — general flag-in-frame workflow
