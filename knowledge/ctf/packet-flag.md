# packet-flag — the flag is inside a decoded frame

The most common H4CKRF CTF pattern. Capture, decode, read the flag out
of a packet's payload.

## The signature

- The band has short packet-like bursts (POCSAG, LoRa, AX.25, Zigbee).
- The challenge text says "listen at frequency X" or "here's a
  capture" without hinting at replay.

## The workflow

1. **Classify** — `analyze_iq_modulation`.
2. **Look up the protocol** — `knowledge_lookup_protocol({name})` for
   the framing rules.
3. **Decode** — the right `decode_*` verb.
4. **Read the payload** — look at the human-readable field.

## Common protocols and where the flag lives

- **POCSAG.** The alphanumeric payload of a message with a specific
  `ric` — often the pager address IS the hint, and the message body
  is the flag. `decode_pocsag` returns both.
- **APRS.** The `comment` field of a position report, the body of a
  message, or the status text. `decode_aprs` returns each with the
  DTI (data-type identifier).
- **Zigbee.** Payload of an application-layer command. H4CKRF does
  not decode above the PHY today; the operator escalates to
  Wireshark / KillerBee.
- **LoRaWAN.** Application-layer payload — encrypted end-to-end.
  H4CKRF captures the PHY; decoding the app payload needs the
  AppSKey, usually leaked in the challenge or in another artifact.
- **ADS-B.** ICAO24 address + callsign; the flag might be a
  specific tail number. `decode_ads_b` returns `icao24_hex` and
  `raw_hex`.

## Trap catalog

- **"The flag is in cleartext."** Usually true for POCSAG and
  APRS. Usually false for LoRaWAN and cellular (encrypted).
- **"CRC-OK means the frame is real."** Needs qualification. A
  short frame can pass CRC by luck; check consistency across
  multiple captures if the frame is critical.
- **"Every field is the flag."** No — most fields are protocol
  metadata (address, sequence number, CRC). The flag is usually in
  a human-readable payload.

## Failure modes

- **Decoded but garbled.** Try flipping polarity, retry at a higher
  sample rate, or check the encoder assumption (Manchester vs PWM).
- **CRC fails on every frame.** You may have the wrong bit order or
  init value; try MSB-first vs LSB-first, and init 0x0000 vs 0xFFFF.
- **No frames returned.** The transmitter is not on the air during
  your capture window. Try a longer `duration_s`, or a wider
  frequency search.

## Cross-references

- `../pocsag-flex/` — POCSAG framing details
- `../aprs/` — APRS DTIs
- `../crc-fec/reference.md` — CRC-16-CCITT and variants
- `records/protocols.json` — the machine-readable per-protocol spec
