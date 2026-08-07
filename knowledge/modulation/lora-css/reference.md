# lora-css/reference.md — LoRa chirp spread spectrum

## Chirp basics

A **linear chirp** sweeps its frequency from `-BW/2` to `+BW/2` (an
"up-chirp") over one symbol period. LoRa uses `2^SF` distinct symbols
per SF (spreading factor) — each symbol is an up-chirp with a
cyclic-shifted start frequency.

- **Symbol duration:** `T_sym = 2^SF / BW` seconds.
- **Bit rate:** `SF · BW / 2^SF` bps (chip-level), before FEC.

## Parameters

| SF | Chip rate | Symbols/s at 125 kHz | Sensitivity (dBm) |
|----|-----------|----------------------|-------------------|
| 7 | 125,000 | 976.6 | -123 |
| 8 | 125,000 | 488.3 | -126 |
| 9 | 125,000 | 244.1 | -129 |
| 10 | 125,000 | 122.1 | -132 |
| 11 | 125,000 | 61.0 | -134 |
| 12 | 125,000 | 30.5 | -137 |

Sensitivity numbers are Semtech's own datasheet claims at 1% PER.

**Bandwidths:** 125, 250, 500 kHz (LoRaWAN common). Some proprietary
LoRa uses 62.5 kHz.

## Dechirp — the receiver's trick

Multiplying the received signal by a reference **down-chirp** (conjugate
of the up-chirp) collapses each symbol to a single tone whose frequency
identifies the symbol:

```python
# reference down-chirp of length N = 2^SF samples
k = np.arange(N)
ref_down = np.exp(-1j * np.pi * (k**2) / N)

# for each symbol, multiply and FFT; peak bin is the symbol value
dechirped = symbol_iq * ref_down
sym_idx = int(np.argmax(np.abs(np.fft.fft(dechirped))))
```

## LoRa PHY layer (post-dechirp)

- **Preamble:** 8 up-chirps.
- **Sync word:** 2 modified symbols (public network = 0x34, private
  networks use different values).
- **SFD:** 2.25 down-chirps ("start of frame delimiter").
- **PHDR:** implicit or explicit; header contains payload length,
  coding rate, CRC bit.
- **Whitening:** LFSR XOR over the payload.
- **Hamming FEC:** rates 4/5, 4/6, 4/7, 4/8.
- **Interleaving + Gray coding** before the whitening.
- **Payload CRC-16.**

**Practically:** decoding LoRa from IQ is well-supported but not fun
to code from scratch. Use `gr-lora_sdr` (EPFL fork) or `sdrangel`.

## LoRaWAN framing (above LoRa PHY)

- **MHDR + FHDR + FPort + payload + MIC.**
- **AES-128 CCM** encrypts the payload (with AppSKey) and MICs the
  frame (with NwkSKey). **The corpus documents the PHY; MAC decoding
  is downstream.**

## Regulatory

- **EU 863-870 MHz:** ETSI EN 300 220. Duty-cycle limits per sub-band
  (0.1% to 10%).
- **US 902-928 MHz:** FCC Part 15 §15.247 spread. 400 ms max dwell
  per channel per 20 s.
- **433 MHz:** shared with amateur / SRD in EU; secondary use in US.

## Citations

- Semtech AN1200.22 — LoRa modulation basics.
- LoRaWAN v1.0.4 / v1.1 specifications.
- `gr-lora_sdr` project (EPFL) — reference PHY implementation.
