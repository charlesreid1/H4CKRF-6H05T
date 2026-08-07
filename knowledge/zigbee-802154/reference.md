# zigbee-802154/reference.md — Zigbee and 802.15.4 PHY

IEEE 802.15.4 is the PHY + MAC standard for low-power short-range
wireless. Zigbee, Thread, and various proprietary mesh networks all
ride on top.

## PHY (2.4 GHz)

The most common 802.15.4 variant.

- **Modulation:** OQPSK (offset-QPSK) with half-sine pulse shaping.
- **Chip rate:** 2 Mchip/s.
- **DSSS:** 32-chip pseudo-random spreading per 4-bit symbol.
- **Effective symbol rate:** 62.5 ksym/s (4 bits per symbol × 32
  chips ÷ 2 chip/bit).
- **Payload bit rate:** 250 kbps.
- **Channel bandwidth:** 2 MHz (occupied).
- **Channels:** 16, numbered 11-26 in the standard.
  - Channel 11: 2405 MHz
  - Channel 12: 2410 MHz
  - ... 5 MHz apart
  - Channel 26: 2480 MHz

## Sub-GHz variants (less common)

- **868 MHz (EU):** BPSK, 20 kbps.
- **915 MHz (US):** BPSK, 40 kbps.
- Rare in practice — 2.4 GHz dominates.

## MAC framing

- **Preamble:** 4 bytes of 0x00.
- **SFD** (Start-of-Frame Delimiter): 1 byte, 0xA7.
- **PHY header:** 1 byte (payload length).
- **MAC frame:** Frame Control (2 bytes) + Sequence Number (1 byte)
  + Addressing fields (variable) + Payload + FCS (2 bytes,
  CRC-16-CCITT).
- **Max PSDU:** 127 bytes.

## Zigbee application layer

- **Network layer:** Adds mesh routing, encryption (AES-128), Trust
  Center management.
- **Application Support Sublayer:** Cluster-based command routing.
- **Endpoint / Cluster** model: like ports and services on IP.
- **Standard clusters:** OnOff (0x0006), LevelControl (0x0008),
  ColorControl (0x0300), Thermostat (0x0201), etc.

## Thread vs Zigbee

Both use 802.15.4 PHY. Thread adds IPv6 (6LoWPAN) and a different
mesh routing protocol. Application layer is completely different.

## Capture recipe

```
# Zigbee channel 15 (Philips Hue default in many countries).
capture_iq(target_freq_hz=2_425_000_000,
           sample_rate_hz=8_000_000,
           duration_s=5.0,
           lna_gain_db=8,
           vga_gain_db=20)

# Recognize OQPSK on the spectrogram:
analyze_iq_spectrogram(iq_path, sample_rate_hz=8_000_000,
                        fft_size=512)
# 2 MHz-wide compact lobe at channel center.
```

## What this MCP can and cannot decode

- **Can:** Recognize 802.15.4 PHY signature (compact OQPSK at 2 MHz
  BW). Confirm channel number by center frequency.
- **Cannot:** Full 802.15.4 demodulation. The chip-level DSSS
  correlation is beyond this MCP's DSP primitives. Use
  `zbdump`, Ubertooth, or a dedicated 802.15.4 sniffer.
- **Cannot:** Zigbee cluster decoding. Requires the Trust Center
  key.

## CTF flag patterns

- **The channel IS the flag** — a Zigbee device on an unusual
  channel (e.g. 25 or 26) hints at a specific vendor.
- **Unencrypted network keys** — some cheap Zigbee devices ship
  with permissive Trust Center policies; sniffed key exchange
  reveals the network key.
- **The Zigbee 3.0 install code** — printed on the device, used
  for pairing. Some CTFs hand it to you.

## Cross-references

- `knowledge/ism-2400/` — the band 802.15.4 lives in
- `knowledge/modulation/` — OQPSK context
- `records/protocols.json:protocol-zigbee-802154` — machine record
