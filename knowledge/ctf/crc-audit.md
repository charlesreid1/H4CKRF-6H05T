# crc-audit — the flag is which packets have valid CRCs

You receive many packets — say, 20 keyfob-like OOK bursts. Most have a
valid CRC. A few have deliberately-corrupted CRCs. The pattern of
valid-vs-corrupted encodes the flag (as a bit stream, or as an ordered
index list, or as timestamps).

## Signature

- **Same PHY for every packet** — same modulation, same symbol rate,
  same length.
- **Payload varies press-to-press** — either random or systematic.
- **A subset of packets has bad CRC** — verifying against the vendor's
  documented CRC polynomial fails.

## Decode workflow

1. Capture the full burst sequence.
2. `decode_manchester` (or whatever matches the PHY) each packet.
3. For each decoded payload, compute the CRC of the payload bytes and
   compare to the CRC bits found in the packet.
4. Emit a per-packet `(idx, crc_ok: bool)` list.
5. Interpret the bit sequence `[crc_ok for each packet]` as:
   - **ASCII bits directly:** every 8 packets = 1 character.
   - **Ordered indices of valid packets:** the list `[0, 3, 7, ...]`
     maps to letters A, D, H, ....
   - **Reversed:** try the bit-inverse if plain reading is nonsense.

## Which CRC?

- **CRC-16-CCITT (poly 0x1021):** most keyfobs and weather stations.
- **CRC-8-CCITT (poly 0x07):** shorter payloads, some TPMS.
- **CRC-32:** WiFi, Ethernet — very unusual on a keyfob-length puzzle.

Use the `records/fec_codes.json` file to look up polynomial + init +
reflect flags per family. Sanity check: pick a packet that "should"
be valid; verify its CRC matches with those parameters.

## Numpy sketch

```python
import crcmod

# CRC-16-CCITT-Kermit
crc16_ccitt = crcmod.mkCrcFun(0x11021, initCrc=0x0000, rev=True, xorOut=0x0000)

crc_status = []
for pkt in decoded_packets:
    payload = pkt[:-2]                        # last two bytes are the CRC
    received_crc = int.from_bytes(pkt[-2:], 'little')
    computed_crc = crc16_ccitt(payload)
    crc_status.append(computed_crc == received_crc)

# interpret crc_status as an ASCII bitstream:
bits = ''.join('1' if s else '0' for s in crc_status)
print(int(bits, 2).to_bytes(len(bits) // 8, 'big').decode())
```

## Sanity checks

- If ~half the packets pass and half fail with no clear pattern, the
  puzzle is not a CRC audit — it's real bit-error noise.
- If *no* packets pass, you have the wrong CRC polynomial or the wrong
  bit ordering. Try `records/fec_codes.json` alternatives.

## Cross-references

- `../crc-fec/reference.md`
- `../records/fec_codes.json`
- `whitening-audit.md` — the sibling puzzle where scrambling, not CRC,
  is the medium
