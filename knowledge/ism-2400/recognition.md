# ism-2400/recognition.md — reading the busiest ISM band

## First-glance archetypes

**A wide flat brick spanning ~20 MHz**
WiFi 2.4 GHz (802.11n or older). Centered on a WiFi channel — check
2412 (ch 1), 2437 (ch 6), 2462 (ch 11).

**A wide flat brick spanning 40 MHz**
WiFi 802.11n bonded 40 MHz mode. Rare in crowded areas.

**Peppered narrow spikes moving across the whole band**
Bluetooth Classic FHSS or an early 802.11 FH device. Each spike is
~1 MHz wide and lasts ~625 μs. If the pattern locks on 2.402, 2.426,
2.480 MHz specifically, it's BLE advertising.

**16 discrete OQPSK signals at 2405-2480 MHz on 5 MHz centers**
Zigbee / 802.15.4.

**A wide analog FM-like blob with visible video sidebands**
Analog FPV video (racing drones, older cameras).

## Bluetooth vs BLE

- **BT Classic:** hops across 79 channels (2402 + n MHz for n =
  0..78). Every packet is on a different channel.
- **BLE:** hops across 40 channels (2402 + 2n MHz). Advertising is
  fixed to 37/38/39 at 2402/2426/2480. Data channels use the
  connection's hop map.

If you see continuous 1 MHz GFSK bursts at exactly 2426 MHz for
seconds at a time, you're watching a BLE advertiser (a fitness
tracker beacon, a smart bulb, an AirTag-like broadcaster).

## WiFi from a distance

You cannot decode WiFi with a HackRF. What you CAN see:

- Presence and rough channel occupancy.
- Beacon-frame timing (every 102.4 ms in the standard).
- Coarse activity level.

For actual WiFi frame decoding, hand off to P1N3NUT5 or a real
monitor-mode adapter.

## The microwave oven

If you're seeing broadband noise across 2440–2470 MHz that comes and
goes on a ~1 Hz duty cycle, it's a microwave oven. Kitchen appliances
are FCC Part 18 industrial, not Part 15 — regulated separately, and
they leak.

## CTF flag patterns

- **BLE advertising packets** contain a manufacturer-data field where
  a CTF payload can hide. Requires a BLE-specific decoder (not this
  MCP).
- **The channel pattern IS the flag.** BLE hop map is derived from
  connection parameters — recovering it recovers the map.
- **Zigbee unencrypted** — some cheap smart plugs and old ZigBee
  devices ship without link keys. Frames are decodable directly.
- **RC control channels** — some hobbyist drone protocols encode
  telemetry (RSSI, battery) in cleartext. FrSky D8/D16 in particular
  has published PHY specs.

## Common pitfalls

- **The 8-bit ADC clips.** Turn off RF amp. Drop LNA to 8 dB. WiFi
  routers at 3 m are usually still too strong.
- **You're seeing your own laptop's WiFi.** Airplane mode + wired
  Ethernet before you sweep, especially if you want a clean
  baseline.
- **The HackRF's 20 Msps ceiling can't span the whole band.** Sweep
  in chunks.
