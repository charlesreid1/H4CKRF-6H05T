# weather-station-flag — an authentic-looking sensor packet with a twist

The bait: a 433 MHz weather-station transmission that looks exactly
like an Acurite / Fine Offset / Oregon Scientific packet. The catch:
one field carries the flag as an out-of-range value or encoded string.

## Signature

- **Carrier:** 433.92 MHz (majority) or 915 MHz (US Ambient Weather).
- **Modulation:** OOK (Acurite, Oregon Scientific) or 2FSK (Fine
  Offset).
- **Symbol rate:** 1000-4000 bps.
- **Packet length:** 56-96 bits typical.

## Decode workflow

1. `capture_iq({freq: 433920000, duration: 30, sample_rate: 2000000})`.
   Weather stations transmit every ~30-60 s.
2. Run `rtl_433 -r capture.cs8 -s 2000000` against the file. If it
   recognizes the packet as a known vendor, the flag is inside the JSON
   output — but almost certainly in an unexpected field.
3. If `rtl_433` doesn't match anything: dump `-A` mode for pulse timing,
   then compare against `records/protocols.json` filtered to
   `category=weather` (records like `protocol-acurite-592txr`,
   `protocol-fine-offset-wh1080`).

## Where the flag hides

- **Sensor ID field:** an ASCII string smuggled through the 8-bit ID
  slot (0x41='A', 0x42='B'...). Read as raw bytes.
- **Temperature:** an implausible reading (`0x666` = -110°C in some
  encodings) that decodes as ASCII.
- **Humidity:** stuck at 0xFF or a 2-digit ASCII value.
- **Checksum override:** a packet with a valid CRC but "impossible"
  physical values (99% humidity + 200°C).
- **Battery flag toggle timing:** the flag = the number of packets
  between battery-low toggles.

## Sanity checks

- **Temperature ranges:** Acurite reports -40°C to +85°C. Fine Offset
  -50°C to +100°C. Anything outside → flag.
- **Humidity:** 0-100%. Anything outside → flag.
- **Wind direction:** 0-360°. Anything outside → flag.
- **Battery status:** boolean; toggles rarely; a rapid toggle sequence
  encodes a bit stream.

## Cross-references

- `../weather-stations/reference.md`
- `../rtl-433/reference.md` — the CLI
- `../records/protocols.json` (weather entries)
- `packet-flag.md` — general framework for "flag in a decoded packet"
