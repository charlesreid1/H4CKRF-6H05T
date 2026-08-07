# rtl-433/walkthrough.md — try every decoder

## HackRF capture → rtl_433 pipeline

```
# 1. HackRF captures at 2 Msps into a .cs8
# (do this through the MCP's capture_iq call, not by shelling out)

# 2. Decimate 2 Msps → 250 ksps for rtl_433
sox --bits 8 --encoding signed-integer --rate 2000000 --channels 2 \
    capture.cs8 --rate 250000 capture_dec.cs8

# 3. Feed rtl_433 in analyzer mode first — dumps pulse timings
rtl_433 -r capture_dec.cs8 -s 250000 -A

# 4. If -A shows a plausible symbol pattern, retry with all decoders
rtl_433 -r capture_dec.cs8 -s 250000 -G -F json
```

## Interpreting -A output

```
Analyzing pulses...
Total count:   72,  width: 2496 ms (624000 S)
Pulse width distribution:
 [ 0]  count:   35,  width:   532 us [521;544] ( 133 S)
 [ 1]  count:   37,  width:  1002 us [990;1015] ( 251 S)
Gap width distribution:
 [ 0]  count:   36,  width:   464 us [451;476] ( 116 S)
 [ 1]  count:   35,  width:   996 us [980;1010] ( 249 S)
```

- Two pulse widths and two gap widths → probably **PWM** (short and
  long).
- One pulse width, two gap widths → probably **PPM** (short and long
  gap between fixed pulses).
- Bit rate ≈ 1 / (short + long) — here `1 / 1.5 ms = ~660 bps`.

This gives you enough to write a targeted numpy decoder if none of
rtl_433's built-in ones match.

## When rtl_433 fires

- **JSON output** — one line per decoded packet:

```json
{"time":"2026-08-07 14:23:11", "model":"Acurite-592TXR", "id":121,
 "channel":"A", "battery_ok":1, "temperature_C":22.3, "humidity":47}
```

- Pipe this into a log, MQTT broker, or a downstream analytics tool.
- For a CTF, grep the JSON for the flag string or an anomaly (unusual
  device ID, weird humidity value, etc.).

## What rtl_433 cannot do

- **CSS / LoRa** — reach for `gr-lora_sdr` or SDRAngel.
- **Continuous-mode protocols (POCSAG, FLEX)** — reach for `multimon-ng`.
- **QPSK / QAM / OFDM** — reach for GNU Radio or a system-specific
  decoder.
- **Encrypted rolling code** — rtl_433 gives you the ciphertext bit
  stream; decryption is out of its scope (and mostly out of the
  corpus's scope too).
