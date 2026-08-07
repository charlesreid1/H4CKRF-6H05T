# weather-stations/reference.md — 433 MHz weather-station vendors

Cheap wireless weather sensors are the most common single class of
radios in the 433 MHz ISM band. Each vendor rolled their own PHY, so
there are hundreds of subtly different protocols. The
[`rtl_433`](https://github.com/merbanan/rtl_433) project ships >200
device decoders — that's the reference catalog.

## Big vendors

### Acurite

- **Bands:** 433.92 MHz, some 915 MHz models.
- **PHY:** OOK, Manchester at 4 kbps.
- **Burst:** 8-repetition sync + 4× repeated 56-bit data packets.
- **Payload:** Device ID + battery flag + temperature (Fahrenheit
  tenths) + humidity byte + optional wind/rain data.
- **Models:** 5-in-1, Atlas, Iris, Rain Wise, tower sensor.

### Fine Offset

- **Bands:** 433.92 MHz (EU) or 915 MHz (US).
- **PHY:** OOK, Manchester at ~2 kbps.
- **Payload:** Device ID + temperature (Celsius tenths) + humidity +
  wind + rain.
- **Rebrands:** Ambient Weather, Ecowitt, some Bresser models — same
  Chinese OEM.

### Oregon Scientific

- **Bands:** 433.92 MHz.
- **PHY:** Multiple generations (v1, v2.1, v3.0), each different.
- **v3.0 payload:** 0xA prefix nibble + device ID + rolling code +
  temperature + humidity + CRC.
- **Models:** THGR122N, BTHR968, etc.

### La Crosse

- **Bands:** 433.92 MHz (EU) or 915 MHz (US).
- **PHY:** OOK Manchester.
- **Rebrands:** TFA, WS-1080, various.

### Bresser

- **Bands:** 868 MHz (some models) or 433 MHz.
- **PHY:** FSK on 868, OOK on 433.
- **Rebrands:** Bresser-branded imports of Fine Offset chipsets.

## Typical protocol shape

Most 433 MHz weather stations share this pattern:

1. Preamble (10-20 ms of `1010...`).
2. Sync word (vendor-specific 8-16 bits).
3. Device ID (4-8 bits, changes on battery replacement).
4. Battery flag (1 bit).
5. Temperature (10-12 bits, tenths of °F or °C).
6. Humidity (7-8 bits, percent).
7. Optional wind/rain/UV bytes.
8. CRC (usually CRC-8 or vendor-specific).

Each burst repeats 3-8 times per transmission for reliability.

## Practical decoder path

The MCP's `decode_manchester` can extract raw bits from most 433 MHz
weather stations. Interpreting those bits requires vendor-specific
knowledge:

```
capture_iq(target_freq_hz=433_920_000, sample_rate_hz=2_000_000,
           duration_s=90.0)   # long capture — data updates every 30-60 s
decode_manchester(iq_path, sample_rate_hz=2_000_000, symbol_rate_hz=4000)
```

Then hand the resulting bit stream to `rtl_433 -a` for vendor
detection, or match against the record files in this corpus.

## Cross-references

- `records/protocols.json` — per-vendor entries
- `knowledge/ism-433/` — the band
- rtl_433 GitHub (external) — reference decoder catalog
