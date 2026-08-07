# lora/reference.md — LoRa PHY

LoRa (Long Range) is Semtech's chirp-spread-spectrum modulation, used
by LoRaWAN and many proprietary LPWAN products. Not to be confused
with LoRaWAN — LoRa is the PHY, LoRaWAN is the MAC/network layer on
top.

## Modulation

- **CSS** (Chirp Spread Spectrum). Every symbol is a chirp: a
  frequency sweep from -BW/2 to +BW/2 (or wrapped around).
- **Channel bandwidths:** 125, 250, 500 kHz standard.
- **Spreading factors (SF):** 7-12. SF7 is fastest / shortest range;
  SF12 is slowest / longest range.
- **Symbol duration:** `2^SF / BW` seconds. SF7@125kHz = 1.024 ms per
  symbol; SF12@125kHz = 32.768 ms.
- **Payload bits per symbol:** SF (7 bits/symbol at SF7, 12 at SF12).

## Frame structure

A LoRa uplink frame:

1. **Preamble.** 8+ upchirps (base-2 up-chirps starting at -BW/2).
2. **Sync word.** 2 upchirps with a specific offset (public network
   = `0x34`, private = `0x12`).
3. **Start-of-frame delimiter.** 2.25 downchirps.
4. **Physical header** (optional, for "explicit" mode). Payload
   length + coding rate + CRC-enable flag.
5. **Payload.** N-byte encrypted payload with optional CRC.
6. **Coding.** Hamming code (4/5 - 4/8 coding rate).

## LoRaWAN

The MAC layer. Adds:

- **DevEUI/AppEUI/DevAddr** (device addressing).
- **AES-CTR encryption** with per-device keys.
- **Adaptive Data Rate** (ADR) — the network picks SF/BW per device.
- **Class A/B/C** device profiles (RX windows).

## Regional bands

| Region | Uplink channels | Downlink RX2 |
|---|---|---|
| EU868 | 868.1 / 868.3 / 868.5 MHz | 869.525 MHz |
| US915 | 64 × 125 kHz + 8 × 500 kHz (902.3-914.9) | 923-928 MHz |
| AU915 | Same as US915 sub-band | 923.3 MHz |
| AS923 | 3-4 channels around 923 MHz | 923.2 MHz |
| KR920 | 3+ channels around 920 MHz | 921.9 MHz |
| IN865 | 3 channels around 865 MHz | 866.55 MHz |

## Capture recipe

```
# EU868 uplink capture — center on 868.3 MHz, need enough BW for
# the chirp to sweep.
capture_iq(target_freq_hz=868_300_000,
           sample_rate_hz=1_000_000,   # comfortably > 125 kHz BW
           duration_s=5.0)

analyze_iq_spectrogram(iq_path, sample_rate_hz=1_000_000,
                        fft_size=256, overlap=0.5)
# peak_freqs_hz should sweep monotonically across time -> chirp.
```

## What this MCP can and cannot decode

- **Can:** Recognize CSS signature via `analyze_iq_spectrogram`
  (diagonal streaks). Estimate chirp period (which reveals SF given
  BW).
- **Cannot:** Full LoRa demodulation. Requires a dedicated decoder
  (`gr-lora_sdr`, `sdrangel`, or a Semtech radio module in
  packet-forwarder mode).
- **Cannot:** LoRaWAN payload decryption. Requires the network's
  session keys.

Hand a captured LoRa `.iq` file to `gr-lora_sdr` after using the MCP
to identify it.

## CTF flag patterns

- **The SF/BW combo IS the flag** (a specific "SF9BW125" recipe is
  the hint).
- **The chirp direction IS the flag** — up vs down chirps at
  unexpected positions.
- **A LoRa payload with the network keys included IS the setup.**
  The CTF hands you both the capture and the AppSKey/NwkSKey; the
  challenge is to run `gr-lora_sdr` and decrypt.

## Cross-references

- `knowledge/modulation/` — CSS in the family table
- `knowledge/ism-868-915/` — the bands LoRa uses
- `records/protocols.json` — LoRaWAN entries per region
