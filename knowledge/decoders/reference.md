# decoders — reference

Line-coding decoders take a real-valued envelope (post-demod) and slice
it into bits. All parameters and per-vendor variants live in
`records/decoders.json`; this file is the prose companion.

## Manchester (IEEE 802.3 / G.E. Thomas)

- **Encoding rule.** Each bit becomes two half-symbols. A transition at
  mid-bit encodes the value.
- **Polarity conventions.**
  - IEEE 802.3: `0 = low→high`, `1 = high→low`.
  - G.E. Thomas: inverse.
- **Self-clocking.** Yes — every bit has a mid-symbol transition.
- **Preamble.** Alternating `0xAA / 0x55` gives a clean clock peak at
  the symbol rate.
- **Failure mode.** If you get `invalid_pairs > num_symbols / 4`, flip
  polarity (`"ieee"` ↔ `"thomas"`). If flipping doesn't help, the
  encoding is probably PWM, not Manchester.

## Differential Manchester

- Mid-bit transition is always present (for clock); a start-of-bit
  transition encodes the bit value.
- **Advantage over plain Manchester:** polarity-independent — the
  decoder does not need to know whether the receiver front-end
  inverted the signal.
- **Use cases:** token ring 802.5, some ISO/IEC 14443 RFID uplinks,
  occasional keyfob variants that resist plain Manchester decoders.

## NRZ (non-return-to-zero)

- **Encoding.** Level directly encodes the bit for the full symbol
  period; no mid-bit transition.
- **Not self-clocking.** A long run of zeros or ones has no
  transitions — the receiver needs an external clock or a preamble.
- **Where it hides.** Post-demod output of 2FSK looks like NRZ bits at
  the symbol rate — that's what `decode_pocsag` runs internally after
  the FSK discriminator.

## NRZI (non-return-to-zero inverted)

- **Encoding.** A transition at the start of a symbol encodes one bit
  value; no transition encodes the other. Value = XOR of previous
  level.
- **Two flavors.**
  - NRZ-mark: `1 = transition`.
  - NRZ-space: `0 = transition`.
- **Use cases.** HDLC / AX.25 (with bit-stuffing after 5 consecutive
  1s), USB PHY, some ISO/IEC 14443 downlinks.

## PWM (pulse-width modulation)

- **Encoding.** Each bit is a fixed-period pulse; the ratio of high
  time to low time encodes the value.
- **Typical params.** `short_us ∈ [200, 800]`, `long_us ∈ [600, 2400]`.
  Ratios are vendor-specific.
- **Use cases.** Chamberlain/LiftMaster garage-door fixed codes, some
  Nexa/HomeEasy 433 MHz remotes, IR remote protocols (NEC, RC-5, Sony
  SIRC), many 433 MHz weather-station formats.
- **`decode_pwm` args.** Pass both `short_us` and `long_us`; the
  validator rejects `short ≥ long`.

## PPM (pulse-position modulation)

- **Encoding.** A short pulse of fixed width; the *gap* between
  successive pulses encodes the bit.
- **Special case.** ADS-B (Mode S) uses PPM at the bit level: 1 μs
  slot, first-half high = 1, second-half high = 0. That's why
  `decode_ads_b` has its own dedicated decoder.
- **Typical params.** `pulse_us ∈ [50, 500]`, gaps in the hundreds to
  low thousands of microseconds.

## PCM (pulse-code modulation) — cross-reference only

Not a line code — a source code. A radio decoder rarely sees raw PCM
off the air; the payload of a digital voice channel (DMR, TETRA, P25)
is a vocoder frame that then feeds NRZ or Manchester on the channel.

## When to pick which decoder

1. Start with `analyze_iq_modulation` — if OOK wins, the line code is
   probably Manchester or PWM.
2. `analyze_iq_symbols` gives you the symbol rate — a Manchester
   symbol appears at *twice* the underlying bit rate. If the estimator
   reports 4 kHz and the vendor spec says "2 kbps," that's Manchester.
3. If Manchester decode returns `invalid_pairs > num_symbols/4` in
   both polarities, try PWM with `short_us ≈ 400, long_us ≈ 800`.
4. If both fail, the encoding may be NRZ or PPM — check
   `records/decoders.json` for the target protocol's known encoding.

## Cross-references

- `knowledge/modulation/` — the family that carries the line code
- `knowledge/demodulators/` — how to get from IQ to envelope/frequency
- `records/decoders.json` — the machine-readable version
- `records/protocols.json` — protocol → line-code mapping
