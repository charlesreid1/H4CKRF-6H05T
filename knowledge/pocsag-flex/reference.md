# pocsag-flex/reference.md — POCSAG and FLEX paging

Two paging protocols that dominated 1980s–2000s and still exist today
in hospital paging, emergency dispatch, and public-safety networks.
Both are 2FSK. Both are *plaintext* in the majority of deployments —
the reason paging is a perennial CTF favorite.

## POCSAG (Post Office Code Standardisation Advisory Group)

CCIR Radio Paging Standard #1. Circa 1982. Simple, universally
deployed, still alive in 2026 for niche uses.

| Property | Value |
|---|---|
| Standard | ITU-R M.584-2 (CCIR RPC1) |
| Modulation | 2FSK, ±4.5 kHz deviation |
| Baud rates | 512, 1200, 2400 |
| Sync word | `0x7CD215D8` (32 bits) |
| Codeword | 32 bits (1 flag + 20 data + 10 BCH + 1 parity) |
| Batch | 1 sync codeword + 8 frames of 2 codewords = 17 codewords |
| Framing | BCH(31,21) error-correcting + even-parity |
| Address bits | 18 in upper codeword + 3-bit frame position = 21 total |
| Function bits | 2 (tone/numeric-BCD/voice-alert/alphanumeric) |
| Payload types | Numeric (4-bit BCD, LSB first), 7-bit ASCII (LSB first) |

Cross-record: `records/protocols.json:protocol-pocsag-1200`.

## POCSAG address structure

The full 21-bit RIC (Radio Identity Code) is derived from the address
codeword's 18 data bits plus the 3-bit frame slot in the batch:

```
RIC = (address_upper18 << 3) | frame_slot
```

Address codewords are recognized by `flag = 0` (bit 31); message
codewords have `flag = 1`.

## POCSAG payload interpretation

- **Function 0:** Tone-only (no payload).
- **Function 1:** Numeric (4-bit BCD, LSB first). 16 code values map
  to `0-9 * U space -` and a few reserved.
- **Function 2:** Voice-alert / tone with voice-channel selection.
- **Function 3:** Alphanumeric (7-bit ASCII, LSB first).

The `decode_pocsag` verb returns both a numeric and an ASCII
interpretation for every message; the operator picks the one that
matches the function bits (or that looks like text).

## FLEX

Motorola's answer to POCSAG's throughput ceiling. 1993. 4FSK with a
smarter framing structure that supports higher rates and roaming.

| Property | Value |
|---|---|
| Standard | Motorola / TIA-102-A |
| Modulation | 4FSK, ±4.8 kHz deviation (2- or 4-level) |
| Baud rates | 1600 (2-level), 3200 or 6400 (4-level) |
| Frame duration | 1.875 s (32 frames per 60 s cycle) |
| Payload | Numeric or alphanumeric, LSB first |
| Sync word | 0xA6C6AAAA (multiple variants per phase) |

FLEX is significantly more complex than POCSAG. This corpus does not
ship a FLEX decoder — for CTFs use `multimon-ng` or `pdw`.

## Typical bands

- **VHF paging:** 138–174 MHz (public safety, hospital, business)
- **UHF paging:** 415–470 MHz (rare in NA; more in EU/APAC)
- **929 MHz paging (US):** 929–932 MHz (paging carriers like Skytel
  in the 90s and 2000s)

## Capture recipe

```
sweep_spectrum(start_freq_hz=929_000_000,
               end_freq_hz=932_000_000,
               dwell_s=1.0)
# Look for continuous 2FSK-like activity in narrow (~12.5 kHz)
# channels.

capture_iq(target_freq_hz=929_662_500,   # typical Skytel channel
           sample_rate_hz=100_000,
           duration_s=30.0)

decode_pocsag(iq_path, sample_rate_hz=100_000, baud=1200)
```

## Legality of decoding

- **US:** Reception is generally legal (Communications Act §705 has
  exceptions for radio comms intended to be heard by the public).
  Redistribution of intercepted personal messages is not.
- **EU:** Varies by country. Sweden and the Netherlands allow
  hobbyist decoding; France explicitly prohibits it.
- **Regardless of jurisdiction:** never TX in a paging band.
- The RiskAssessor does not BLOCK paging bands for TX (no
  safety-of-life allocation), but the operator must respect local law.

## Cross-references

- `records/protocols.json:protocol-pocsag-*`
- `knowledge/modulation/` — 2FSK primer
- `../../src/hackrf_agent/hw/analysis.py` — `decode_pocsag`
  implementation
