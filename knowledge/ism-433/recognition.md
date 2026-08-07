# ism-433/recognition.md — the "just decode this waterfall" band

## Sweep first impressions

Almost any suburban sweep of 433 MHz will show:

- **A busy 433.92 MHz** with dozens of narrow OOK bursts per minute —
  weather stations, doorbells, various IoT.
- **Occasional keyfob press** (short train of 3–5 bursts).
- **Continuous background clutter** from LED bulbs, DC-DC converters,
  and cheap chargers.

## Burst archetypes

**Long, structured 15-30 ms bursts every 40-60 seconds**
Weather station. Try each vendor decoder in `rtl_433`. Acurite is
common in NA; Fine Offset dominates EU.

**Short burst train (3–5 bursts, 30-80 ms each, 20 ms gaps)**
Keyfob press. Rolling-code Keeloq has an incrementing 32-bit counter
in the payload. Fixed-code is just the same bits every time.

**Repeated identical burst at 1-second cadence**
Wireless doorbell "button held" mode, or a cheap sensor beacon.

**Single sinc-shaped narrow lobe with no modulation**
Someone's remote is stuck.

**A wide sinc that spans 500 kHz+**
Probably not §15.231-compliant. Could be a poorly-filtered cheap
transmitter or LoRa on the 433 MHz sub-channel.

## Weather-station tells

- **Acurite:** 4 kbps OOK Manchester, ~90 ms burst, unique sync word
  per vendor. Payload includes a 6-bit device ID and temperature in
  Fahrenheit tenths.
- **Fine Offset (EU):** Similar bitrate, different sync. Temperature
  in Celsius tenths, humidity as raw byte.
- **Oregon Scientific v2.1/v3.0:** Manchester, complicated preamble.
  A specific `0xA` nibble prefix identifies v3.

## Common decoder recipe

```
capture_iq(target_freq_hz=433_920_000, sample_rate_hz=2_000_000,
           duration_s=30.0)
analyze_iq_modulation(iq_path)         # OOK
analyze_iq_symbols(iq_path, sample_rate_hz=2_000_000)  # ~1-4 kHz
decode_manchester(iq_path, sample_rate_hz=2_000_000, symbol_rate_hz=<estimate>)
# If Manchester fails, try PWM:
decode_pwm(iq_path, sample_rate_hz=2_000_000, short_us=500, long_us=1000)
```

## CTF flag patterns

- Bit stream contains ASCII text → probably a doorbell or DIY module.
- Bit stream is 24-32 bits with a plausible temperature in the middle
  → weather station. The flag might be in the vendor/device-ID
  bits.
- Bit stream repeats with a 32-bit incrementing counter → Keeloq
  rolling code. Flag is often in the vendor-code preamble.
- 100% duplicate bursts across a whole capture → fixed-code. Legally
  and technically the easiest replay target.

## Common pitfalls

- **Concurrent transmitters** — a busy 433 MHz sweep often has
  overlapping bursts. Isolate one at a time.
- **Vendor-specific sync words** — a burst decoded to garbled bits
  usually means the wrong endianness or byte alignment. Try
  `decode_manchester` with `polarity='thomas'`.
- **DC spike** — always use `target_freq_hz`.
