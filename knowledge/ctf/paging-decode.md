# paging-decode — POCSAG/FLEX with a flag in the message

Pagers are historically CTF-relevant because they're plaintext, 2FSK,
and their bit-level format is well-documented. The flag lives in the
alphanumeric payload.

## The signature

- **Band.** Roughly 138-174 MHz (VHF paging) or 929-932 MHz (US 900
  MHz paging).
- **Modulation.** 2FSK with ~4.5 kHz deviation.
- **Symbol rate.** 512, 1200, or 2400 baud (POCSAG); 1600 or 3200
  baud (FLEX).
- **Preamble.** POCSAG sync word `0x7CD215D8` before every batch.

Look for two parallel spectral lines separated by ~9 kHz peak-to-peak
and short (~30 ms) burst structure.

## The workflow

1. **Capture** with `target_freq_hz` centered on the paging channel
   and `sample_rate_hz=2_000_000`, `duration_s=1-5`.
2. **Confirm 2FSK** with `analyze_iq_modulation`.
3. **Decode POCSAG** at each of the three bauds (512, 1200, 2400)
   until one succeeds:

```jsonc
decode_pocsag({iq_path, sample_rate_hz: 2_000_000, baud: 1200})
// -> {"messages": [{"ric": 123456, "function": 3, "payload_numeric": "...", "payload_alpha": "flag{...}"}]}
```

4. **Read the alphanumeric payload.** A `function` of 3 is
   alphanumeric; function 0 is numeric (BCD-encoded).

## Common CTF patterns

- **Flag in the alphanumeric field.** Most common — the message body
  IS the flag.
- **Flag in the RIC.** The pager address is a memorable-looking
  number (e.g. `1337000`) or a decimal encoding of ASCII.
- **Flag across multiple RICs.** Each RIC gets one letter; assemble
  by sorted RIC.
- **Multi-baud puzzle.** Two POCSAG streams at different bauds on
  the same frequency — captures split by symbol rate.

## Trap catalog

- **"POCSAG only comes at 1200 baud."** False. 512 and 2400 also
  exist. Try all three.
- **"FLEX is the same as POCSAG."** No. FLEX uses 4FSK (four
  levels), different framing, Reed-Solomon FEC. Not in H4CKRF's
  decoder set; escalate to `multimon-ng`.
- **"An empty POCSAG message is a decoder bug."** Sometimes true —
  but idle codewords in POCSAG are `0x7A89C197`; a decoder returning
  an empty payload after seeing many idles is doing the right thing.

## Failure modes

- **`decode_pocsag` returns 0 messages but the band is active.**
  Try all three bauds. Try recapturing with a wider band. Check the
  polarity — some capture chains invert.
- **BCH failures on every codeword.** The signal is 2FSK but not
  POCSAG. Try FLEX (needs external tool) or ACARS (VHF at 131.55
  MHz).

## Cross-references

- `../pocsag-flex/` — full protocol reference
- `records/protocols.json` — POCSAG record IDs
- `packet-flag.md` — general "flag in a frame" workflow
