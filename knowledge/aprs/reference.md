# aprs/reference.md — Automatic Packet Reporting System

APRS is a payload convention layered on AX.25 UI frames. Amateur
operators broadcast position, status, weather, telemetry, and
short messages; digipeaters and IGates propagate frames globally.

## Band

| Region | APRS frequency |
|---|---|
| US / Canada | 144.390 MHz |
| EU | 144.800 MHz |
| Australia / NZ | 145.175 MHz |
| Japan | 144.640 MHz |

All amateur-band; Part 97 license required to TX.

## PHY

- **Modulation:** Bell 202 AFSK-1200 over analog FM voice.
  - Tones: 1200 Hz (space) and 2200 Hz (mark).
  - Bit rate: 1200 bps.
- **Framing:** HDLC (AX.25 layer 2). NRZI, bit-stuffing after 5 ones,
  CRC-16-CCITT FCS, 0x7E flag delimiters.
- **Faster variants:** 9600 bps direct FSK on some VHF/UHF
  frequencies; less common in APRS specifically.

## AX.25 address block

- **Destination.** Usually `APRS` or a version identifier
  (`APDR15` = APRSdroid v1.5, `APOTW1` = OpenTracker, etc.).
- **Source.** The operator's callsign + SSID.
- **Digipeater path.** Up to 8 stations that repeated the frame.
  `WIDE1-1`, `WIDE2-2`, `RELAY` are common alias patterns.

## APRS payload — data type identifiers

The first byte of the info field determines the payload interpretation
(see `decode_aprs` for the full list):

| DTI | Meaning | Example |
|---|---|---|
| `!` | Position no-timestamp, no-messaging | `!4903.50N/07201.75W-` |
| `=` | Position no-timestamp, with messaging | `=4903.50N/07201.75W-` |
| `/` | Position with timestamp, no-messaging | `/092345z4903.50N/07201.75W-` |
| `@` | Position with timestamp, with messaging | `@092345z4903.50N/07201.75W-` |
| `>` | Status | `>My status text` |
| `:` | Message | `:WX1XYZ   :Message text` |
| `;` | Object | `;OBJECT   *092345z4903.50N/...` |
| `)` | Item | `)ITEM!4903.50N/07201.75W-` |
| `T` | Telemetry | `T#123,100,101,102,103,104,00000000` |
| `_` | Positionless weather | `_09231234c...` |
| `$` | Raw GPS (NMEA) | `$GPGGA,...` |

## Position format (uncompressed)

`DDMM.mmH SYM_TABLE DDDMM.mmH SYM_CODE [comment]`

- 8 chars latitude: 2 digits degrees + `MM.mm` minutes + `N` or `S`.
- 1 char symbol table (`/` primary, `\` alternate).
- 9 chars longitude: 3 digits degrees + `MM.mm` minutes + `E` or `W`.
- 1 char symbol code (see APRS symbol tables — `>` = car, `-` =
  house, `[` = jogger, etc.).
- Optional comment.

## Compressed position (rare in modern use)

- 13 chars, base-91 encoded. Higher precision, less human-readable.

## Digipeater path aliases

- **`WIDE1-1`:** local digipeat.
- **`WIDE2-2`:** two-hop wide-area digipeat.
- **`RELAY`:** legacy alias for a single-hop repeater.
- **The digipeater strips 1 from the counter each hop** — when it
  reaches 0, no more digipeats.

## Capture recipe

```
capture_iq(target_freq_hz=144_390_000,   # US APRS
           sample_rate_hz=48_000,        # audio-band rate
           duration_s=30.0,
           lna_gain_db=16,
           vga_gain_db=20)

decode_aprs(iq_path, sample_rate_hz=48_000, baud=1200)
```

The `decode_aprs` handler returns per-frame:

- `destination`, `source`, `digipeaters` (parsed callsigns + SSIDs).
- `control`, `pid`, `is_ui`.
- `info_ascii` (the raw APRS payload).
- `crc_ok` (was CRC-16-CCITT clean?).
- `aprs` dict with `kind` (position/status/message/...) and
  parsed fields (lat, lon, comment, ...).

## CTF flag patterns

- **The comment IS the flag** — `-Flag{...}` after the symbol code.
- **The lat/lon IS the flag** — a specific coordinate encodes a
  location.
- **The callsign IS the flag** — a made-up call like `KG9CTF-13`.
- **The status IS the flag** — after DTI `>`.
- **The digipeater path IS the flag** — an unusual alias like
  `MAGIC-1` in the path.
- **Telemetry values ARE the flag** — telemetry frames carry up to
  5 analog channels + 8 digital bits.

## Cross-references

- `src/hackrf_agent/hw/analysis.py` — `decode_aprs` implementation
- `records/protocols.json` — AX.25 + APRS entries
- Bob Bruninga's original APRS specification (aprs.org)
