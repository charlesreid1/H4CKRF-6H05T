# lora-flag — a LoRa chirp with a flag in the dechirped payload

Recognize LoRa on the waterfall (parallel diagonal streaks). Dechirp
and decode to extract the payload. The flag may be in the raw payload
(LoRa PHY) or inside a LoRaWAN application-layer message.

## Signature

- **Waterfall:** unmistakable parallel diagonal streaks. Slope
  `= BW / T_sym = 2^SF / BW`.
- **Carrier:** 433 MHz (EU sub-band), 868 MHz (EU LoRaWAN), 915 MHz
  (US LoRaWAN).
- **Bandwidth:** 125, 250, or 500 kHz.
- **Spreading factor:** SF 7-12.

## Decode workflow

1. `capture_iq({freq: 868100000, duration: 3, sample_rate: 1000000})`.
   Sample rate at least 2× the LoRa bandwidth.
2. Identify SF and BW from the spectrogram (or `analyze_iq_modulation`).
3. **Preferred:** hand off to `gr-lora_sdr` in GNU Radio, or use
   SDRAngel's built-in LoRa decoder.
4. **Numpy-only sketch (single-symbol proof-of-concept):** see
   `../modulation/lora-css/walkthrough.md`.

## Where the flag hides

- **Raw LoRa PHY payload:** if the packet is *not* LoRaWAN, the payload
  is plaintext. The flag is straightforwardly in the decoded bytes.
- **LoRaWAN payload:** encrypted with AES-128 CCM. The flag is *not*
  in the packet payload without keys. But it might be:
  - In the **DevEUI** / **AppEUI** (unencrypted) — read as ASCII.
  - In the **FPort** field (unencrypted) — could encode a value.
  - In the **DevAddr** (unencrypted after join).
  - In the **timing** — packet arrival intervals encoding morse or bits.
- **Preamble length:** non-standard preamble length can encode a byte.
- **Sync word:** non-standard (public LoRaWAN = 0x34; deviations may
  encode bytes).

## Sanity checks

- LoRa PHY payload with a valid CRC-16 → flag is likely in the payload.
- Payload high-entropy AND MIC field looks valid → LoRaWAN-encrypted;
  look at the frame header instead.

## Cross-references

- `../modulation/lora-css/reference.md`
- `../lora/reference.md`
- `../records/protocols.json::protocol-lorawan-eu868` and `-us915`
- `packet-flag.md` — general "flag in a decoded packet"
