# pocsag-flex/recognition.md — spotting paging on a waterfall

## POCSAG in the wild

**Two-lobe 2FSK bursts on a 12.5 kHz channel**
Classic POCSAG. Bursts last a few seconds (a full batch is ~750 ms at
1200 baud). Between batches, the transmitter is idle.

**Continuous transmission with periodic idle-codeword patterns**
A busy paging carrier. `decode_pocsag` will find lots of sync words.

**Very narrow-shift 2FSK (~4.5 kHz)**
Almost certainly POCSAG. FLEX has ±4.8 kHz deviation and is subtly
wider; casual inspection can't distinguish.

## POCSAG vs FLEX

Fast tests:

1. **Baud test.** POCSAG is 512, 1200, or 2400 baud. FLEX is 1600,
   3200, or 6400. If `analyze_iq_symbols` returns near 1600 or 3200,
   FLEX. Near 1200, POCSAG.
2. **Frame structure.** POCSAG has a rigid 8-frame batch after each
   sync (0x7CD215D8). FLEX uses a phase structure and rolling
   idle codewords.
3. **When in doubt, run `decode_pocsag`.** If it finds no sync
   offsets, the signal isn't POCSAG. Try `multimon-ng` for FLEX.

## Reading `decode_pocsag` output

```
result = decode_pocsag(iq_path, sample_rate_hz=100_000, baud=1200)
result["sync_offsets"]      # list of bit indices where 0x7CD215D8 hit
result["num_codewords"]     # 16 per batch (should be a multiple of 16
                            # if the capture is clean)
result["invalid_codewords"] # BCH failures — expect 0 in clean captures
result["messages"]          # list of {ric, function, numeric, alpha, ...}
```

The verb returns BOTH the numeric-BCD and 7-bit-ASCII interpretations
for every message. The `function` field hints which one the pager
used:

- function 0 → tone-only (both interpretations meaningless)
- function 1 → numeric (use `numeric`)
- function 2 → voice alert (either)
- function 3 → alphanumeric (use `alpha`)

## CTF flag patterns

- **The message text IS the flag.** Alphanumeric POCSAG pages
  historically carried short lines of text. A CTF might inject a
  flag string as the payload of a fake pager.
- **The RIC IS the flag.** A specific 21-bit address might encode
  something meaningful (a phone number, a hex string, a date).
- **The function bits ARE the flag.** Unusual function-bit values
  might indicate a stego channel.
- **Multiple channels ARE the flag.** Some CTFs deliver POCSAG on a
  weird band (932 MHz, 415 MHz) and the challenge is finding it in
  a sweep before decoding.

## Common pitfalls

- **Wrong polarity.** `decode_pocsag` tries both polarities and picks
  the one with more sync-word hits. If both come up empty, the input
  isn't POCSAG (or the SNR is too low).
- **Wrong baud.** Try all three: 512, 1200, 2400. Some transmitters
  step through them.
- **Too narrow a capture bandwidth.** POCSAG occupies about 10 kHz;
  a 100 kHz sample rate is plenty. Higher rates just waste storage.
- **Confusing FLEX for POCSAG.** They look similar. Try both
  decoders.

## When you find real traffic

Legality aside — real paging traffic is often a mix of:

- Doctor / hospital dispatch ("Room 315 code blue")
- Utility company alerts ("Sub 12 breaker trip")
- Numeric SCADA telemetry ("temperature=045")
- The occasional test message ("this is a test")

Do not redistribute personal messages you intercept.
