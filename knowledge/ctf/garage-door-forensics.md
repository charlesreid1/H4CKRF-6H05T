# garage-door-forensics — reverse-engineer a fixed or rolling opener

Three captures of the same opener, in some order. Figure out:

- Is it fixed-code or rolling-code?
- If rolling, is the counter linear (Keeloq-style) or scrambled
  (crypto-authenticated)?
- What's the vendor?

## Signature

- **Carrier:** typically 315 (US) or 390 (older US) or 433.92 (EU),
  occasionally 310, 300, or 27 MHz on legacy hardware.
- **Modulation:** almost always OOK.
- **Symbol encoding:** Manchester or PWM.
- **Symbol rate:** 2-4 kbps typical.
- **Burst structure:** 3-5 repeats per press with short gaps.
- **Packet length:** 40-72 bits.

## Decode workflow

1. `capture_iq({freq: 315000000, duration: 3, sample_rate: 2000000})`
   during a real press (or hand-crafted playback of a captured file).
2. `analyze_iq_modulation(iq_path)` → confirm OOK.
3. `analyze_iq_symbols(iq_path)` → symbol rate estimate.
4. `decode_manchester(iq_path, symbol_rate_bps=...)`. If invalid pairs
   ratio is high, try `decode_pwm` (Chamberlain legacy) or invert
   Manchester polarity.
5. Repeat for two more captures to identify counter behavior.

## Verdict from three captures

- **All three identical:** fixed-code (Chamberlain S+1.0, older Genie,
  early Nexa). *Replay works — subject to law + consent.*
- **Last N bits (typically 16-32) increment by 1 each press:** rolling
  code (Keeloq NLFSR, Chamberlain S+2.0, Genie Intellicode). Fresh
  replay defeated by receiver counter. RollJam is the historical
  attack model, but ships nowhere in this corpus.
- **Bits scrambled unpredictably each press:** cryptographic-rolling
  (Keeloq-AES, modern Chamberlain, Ford post-2015). No fresh-replay
  attack.

## Vendor from framing

- **Chamberlain Security+ 2.0:** 4 kbps Manchester, 40-bit encrypted
  payload + 32-bit counter, sync pattern `0xA5`. Records
  `keyfobs.json::keyfob-chamberlain-security-plus-2`.
- **Genie Intellicode:** 2 kbps Manchester, Keeloq-family framing.
  Records `keyfob-genie-intellicode`.
- **HomeLink:** learns whatever it's given — will match the vendor of
  the fob it was trained on. Not itself a distinct PHY.
- **Nexa (EU):** 250 bps PWM, ~40-bit fixed code.

## Cross-references

- `../keyfobs/reference.md`
- `../garage-doors/reference.md`
- `../records/keyfobs.json`
- `unknown-keyfob.md` — broader "is this any keyfob" triage
