# keyfobs/recognition.md — is this fob fixed, rolling, or novel?

## The three-press test

Capture three consecutive presses of the same fob. Compare the bit
streams:

**All three identical (bit-for-bit)** → fixed code. Replay works.
Most systems this old aren't worth replaying — the flag is usually
that the operator recognizes the vulnerability.

**Three bit streams with one 32-bit region incrementing by 1** →
Keeloq rolling code. The incrementing region is the encrypted counter.
Replay is defeated by counter comparison at the receiver, but
RollJam-style capture-then-jam remains possible.

**Three bit streams with the incrementing region larger (48+ bits)
or with additional random-looking data** → HITAG2 or AES rolling.
More sophisticated countermeasures.

**Three bit streams identical BUT the fob was pressed while near the
car** → PKE challenge-response, not a static press. The RF traffic is
initiated by the car, not the fob. Different attack model entirely.

## Waterfall archetypes

- **Short 30–100 ms burst train** — most keyfobs. Multiple bursts per
  press (3–5 at 20 ms intervals).
- **Two frequencies alternating** — some Ford / GM dual-frequency
  designs. 315 MHz for NA vehicles, 433 for EU, some vehicles both.
- **Non-standard band** — Tesla Model 3 uses 433 for the keyfob but
  the actual door-lock ties to the phone's BLE. Some Nissan/Toyota
  Asian-market models use 312 MHz.
- **No fob press but the car unlocks** — PKE. Different signal chain
  entirely.

## Decoding pipeline

```
sweep_spectrum(start_freq_hz=310_000_000, end_freq_hz=320_000_000, dwell_s=0.5)
sweep_spectrum(start_freq_hz=433_000_000, end_freq_hz=435_000_000, dwell_s=0.5)
# Find where the fob transmits.

capture_iq(target_freq_hz=315_000_000,     # or 433_920_000
           sample_rate_hz=2_000_000,
           duration_s=10.0)

analyze_iq_modulation(iq_path)
# Expect OOK on top.

analyze_iq_symbols(iq_path, sample_rate_hz=2_000_000)
# Symbol rate usually 2000-4000 Hz.

decode_manchester(iq_path, sample_rate_hz=2_000_000,
                  symbol_rate_hz=2048.0)
```

Then look up the vendor in `records/keyfobs.json`:

```
knowledge_lookup_modulation("OOK")
# The record links to the keyfobs.json entries relevant to this PHY.
```

## CTF flag patterns

- **The fob is fixed-code and the payload IS the flag.** Decode
  Manchester → ASCII decoded bits contain readable text.
- **The counter delta IS the flag.** Rolling-code fob, but the
  counter increments by a suspicious amount per press (should be 1).
- **The vendor serial IS the flag.** Keeloq payloads have a 28-bit
  serial in cleartext — a specific value might encode text.
- **The frequency IS the flag.** A fob transmitting at an unusual
  frequency (312.65 MHz, 434.15 MHz) hints at a specific vendor.
- **The number of bursts per press IS the flag.** Some vendors send
  exactly 4, some 5, some 8. Fingerprinting.

## Common pitfalls

- **Capture the whole press.** A 500 ms capture misses the last
  bursts of the press train. Go for 3-5 seconds.
- **RollJam is out of scope for this MCP.** The MCP is half-duplex —
  can't RX and TX simultaneously. RollJam requires a two-radio
  setup.
- **Don't confuse the fob RX with the car's LF interrogation.** Cars
  transmit at 125 kHz LF to wake up the fob for PKE. This MCP can't
  RX that (HackRF's low-frequency floor is ~10 MHz in practice).
