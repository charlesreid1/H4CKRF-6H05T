# crc-fec — reference

Cyclic redundancy checks and forward error correction show up at the
end of most decoded RF frames. This is the reference for the CRC
polynomials and FEC codes H4CKRF actually needs.

## CRC — what and how

A cyclic redundancy check is a hash computed by polynomial division in
GF(2). The transmitter appends the CRC; the receiver recomputes and
compares.

- **CRC-8 (0x07, x⁸ + x² + x + 1).** DVB-S2, some legacy protocols.
- **CRC-8-CCITT (0x8D).** SMBus, some sensors.
- **CRC-16-CCITT (0x1021, x¹⁶ + x¹² + x⁵ + 1).** XMODEM, HDLC, AX.25,
  Zigbee. The most common CRC on the air. Init value varies (0x0000,
  0xFFFF, 0x1D0F depending on protocol); most receivers try both.
- **CRC-16-IBM (0x8005).** USB, Modbus, some LoRaWAN payloads.
- **CRC-24 (0xFFF409).** ADS-B Mode S. Also used as an implicit
  interleaver — the sum of message + CRC modulo the polynomial is
  the ICAO24 address on some downlink formats, so a "CRC fail" can
  mean "wrong ICAO24" not "corrupt bits."
- **CRC-32 (0x04C11DB7 or 0xEDB88320 reversed).** Ethernet, WiFi
  payloads, WAV files.

### How to verify

Every decoder in `hackrf_agent.hw.analysis` returns a `crc_ok` flag per
frame. When it fails on a frame you're sure is real, check:

1. **Preamble alignment.** A one-bit-off preamble corrupts the CRC.
2. **Bit ordering.** LSB-first vs MSB-first; HDLC packs LSB-first.
3. **Init value.** Try `0x0000`, `0xFFFF`, `0x1D0F`.
4. **XOR-out value.** Some protocols XOR the final CRC with a
   constant (usually `0x0000` or `0xFFFF`).
5. **Which bytes.** Header-only? Header + payload? Some protocols
   compute CRC over a subset.

## FEC — the codes H4CKRF cares about

### Hamming (7,4) and (8,4)

Corrects single-bit errors in a 4-bit dataword. Used inside larger
frames as a per-nibble hedge. POCSAG's per-codeword parity is a
Hamming-like SEC.

### BCH — the POCSAG workhorse

- **BCH(31, 21).** Encodes 21 data bits into 31 bits with a
  distance-5 code. Corrects up to 2 bit errors per codeword. Each
  POCSAG codeword is BCH(31, 21) + one even-parity bit → 32 bits.
- **Decoder recipe.** Compute the syndrome (matrix multiply against
  the parity-check matrix); syndrome zero = no error; single-bit
  errors → flip the bit whose syndrome column matches.
- **Failure mode.** Two-bit errors are correctable but three-bit
  errors flip to *the wrong* codeword — you'll get a "successful"
  decode of the wrong message. This is why POCSAG receivers report
  per-codeword BCH validity.

### Reed-Solomon (255, k)

Used inside FLEX paging (over 32-bit blocks) and satellite downlinks
(NOAA APT, CCSDS deep-space). Byte-oriented; corrects `(255 - k) / 2`
byte errors. H4CKRF does not ship an RS decoder — the corpus notes it
so the assistant recommends the right external tool.

### Convolutional codes + Viterbi

Used in GSM downlink, DMR, and TETRA. Rate 1/2 with constraint length 7
is standard. Decoding via the Viterbi algorithm — trellis search over
the encoder's state graph. H4CKRF flags these but does not implement
them; escalate to `osmocom-analog` or `gr-osmosdr` for these
protocols.

### LDPC / turbo — mentioned only

LTE and 5G downlinks. Out of scope for the H4CKRF corpus.

## The trap catalog

- **"CRC-16 is CRC-16"** — needs qualification. IBM, CCITT, and X.25
  variants use different polynomials; a mismatched variant scores
  `verify_claim("CRC-16 is CRC-16") → needs_qualification`.
- **"BCH corrects three errors"** — false for BCH(31,21). The
  distance-5 code guarantees 2 errors and detects 3; three-bit
  patterns can flip to another valid codeword.
- **"Reed-Solomon is a general error correcter"** — needs
  qualification. RS is byte-oriented and works best on burst errors,
  not random single-bit flips.

## Cross-references

- `knowledge/decoders/` — decoders that consume post-FEC bytes
- `knowledge/pocsag-flex/reference.md` — POCSAG's BCH details
- `knowledge/ads-b/reference.md` — CRC-24 with `0xFFF409`
- `records/protocols.json` — every protocol's CRC/FEC per-record
