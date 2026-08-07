# dump1090-readsb/reference.md — the CLI surface

## Input

- **rtl-sdr live:** default. `--device-index 0`.
- **File input (dump1090 --ifile):** legacy dump1090 accepts `.cs8` /
  `.cu8` via `--ifile`.
- **HackRF via GNU Radio bridge:** capture to `.cs8`, then feed
  `dump1090 --ifile capture.cs8 --iformat sc16` (adjust format string).

## Output

- **HTTP web UI** at `:8080` — live aircraft table + map.
- **Beast** binary format for downstream feeders (FlightAware, ADS-B
  Exchange, etc.).
- **AVR** hex text format (`--net-ro-port 30002`).
- **SBS-1** simple text format (`--net-sbs-port 30003`).
- **JSON API** at `:8080/data/aircraft.json`.

## Framing

- **Long frame (DF17/18):** 112 bits, 120 μs airtime, PPM at 1 Mbps.
- **Short frame (DF11/DF4/DF5):** 56 bits, 64 μs airtime.
- **CRC-24** with Mode S parity polynomial (`0xFFF409`).

## What's inside DF17 (the ADS-B extended squitter)

- Bits 1-5: DF (Downlink Format) = 17.
- Bits 6-8: CA (Capability).
- Bits 9-32: ICAO24 aircraft address.
- Bits 33-88: ME (Message field) — the actual ADS-B payload:
  - Type 1-4: aircraft identification (callsign).
  - Type 9-18: airborne position (CPR-encoded lat/lon + altitude).
  - Type 19: airborne velocity.
  - Type 5-8: surface position.
- Bits 89-112: CRC-24 (parity).

## Companion tools

- **readsb** — modern maintained fork; the one you want in 2026.
- **tar1090** — modern web UI overlay for readsb.
- **piaware** — FlightAware feeder.
- **gr-air-modes** — GNU Radio equivalent, historical.
- **pyModeS** — Python library for offline Mode S decoding.

## Legal note

- **RX:** unrestricted in most jurisdictions.
- **TX:** BLOCKED at the safety gate. **1090 MHz is aviation safety;
  never transmit.** Not even for testing. If you need to test an ADS-B
  receiver, use a dedicated aviation-authorized transmit tester or a
  screen room.

## Citations

- readsb GitHub (wiedehopf/readsb).
- dump1090 lineage: mutability -> MalcolmRobb -> flightaware -> readsb.
- RTCA DO-260B (ADS-B MOPS).
