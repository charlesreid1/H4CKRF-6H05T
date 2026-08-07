# ads-b/recognition.md — spotting Mode S traffic

## Waterfall

At 1090.0 MHz in almost any populated area you'll see:

- Short bursts every few milliseconds during busy hours.
- Bursts are ~120 μs long (long frame + preamble).
- No wide-band signature — Mode S is narrow (~2 MHz occupied
  bandwidth from the pulse-shape sidelobes).

## Signal signature

- **Preamble first.** 8 μs of specific pulse pattern before the
  payload. `decode_ads_b` uses correlation against this pattern to
  find frame starts.
- **Very consistent amplitude.** Aircraft transponders are calibrated
  to 250 W output; the envelope after the preamble is a clean
  sequence of ~250 ns pulses.
- **Never quiet for long.** In a metro area, you get 10+ frames per
  second.

## Confirming a decode

`decode_ads_b` returns per-frame:

- `df` — DF17 is ADS-B extended squitter (position/velocity).
- `icao24_hex` — 6-hex ICAO24 address. Look this up on
  [opensky-network.org](https://opensky-network.org) to cross-check.
- `raw_hex` — the 14-byte message. Copy-paste into pyModeS or the
  ADS-B decoder of your choice to get lat/lon/altitude/callsign.
- `crc_ok` — True means the CRC-24 was clean.

If `crc_ok` is False and you're seeing a real airport, the antenna is
probably fine but the frames are getting corrupted. Check for ADC
clipping (drop RF amp), or move the antenna.

## CTF flag patterns

- **The ICAO24 IS the flag** — an aircraft's specific tail number
  encoded in the address.
- **The Callsign IS the flag** — DF17 type code 1-4 messages carry
  the flight callsign (8 6-bit chars).
- **A staged ADS-B recording IS the setup** — the puzzle handed you a
  `.iq` file and wants a specific squawk or callsign extracted.
- **The BLOCKED-band restriction IS the trap** — the puzzle appears
  to ask for TX. It doesn't. Decode-only.

## Common pitfalls

- **sample_rate_hz too low.** 1 MHz is insufficient for 0.5 μs chip
  resolution. 2 MHz is minimum; 4 MHz is more forgiving.
- **CRC keeps failing.** Front-end nonlinearity. Drop LNA gain, add a
  1090 MHz filter, or move away from cellular basestations.
- **You "see" aircraft on `flightradar24` but decode returns 0
  frames.** Your antenna is unmatched (VSWR too high) or the LNA/VGA
  gains are wrong. `hackrf_info` should show clean device state
  first.
- **Trying to TX on 1090.** The gate will refuse. Don't retry with
  different args — read the BLOCKED response and stop.
