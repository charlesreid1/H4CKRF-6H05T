# hackrf-hardware/reference.md — the HackRF One

Great Scott Gadgets' open-hardware SDR transceiver. What the numbers say
you can do with it, and where the ceilings are.

## The block diagram

```
Antenna ┬── RF amp switch (0 / +14 dB) ─┐
        │                                │
        │  RX path                       │
        │  LNA (MAX2837, 0–40 dB, 8 dB   │
        │       steps)                   │
        │  Baseband LPF                  ├── MAX5864 ADC/DAC (8-bit, 20 Msps)
        │  VGA (0–62 dB, 2 dB steps)     │           │
        └────────────────────────────────┘           │
                                                     │
                                              Xilinx CoolRunner II CPLD
                                                     │
                                              LPC4320 ARM Cortex-M4
                                                     │
                                                USB 2.0 (Full/Hi-Speed)
                                                     │
                                                    Host
```

The mixer is **MAX2837** (2.3–2.7 GHz direct-conversion transceiver) +
**RFFC5072** (translation mixer, 85–5900 MHz). The two combined give the
full 1 MHz–6 GHz operating range.

## Specifications

| Parameter | Value |
|-----------|-------|
| Frequency range | 1 MHz – 6 GHz (some units usable down to ~10 kHz with degraded performance) |
| Sample rate | 2 – 20 Msps (quadrature, complex) |
| ADC/DAC resolution | 8-bit interleaved I/Q |
| Instantaneous bandwidth | Up to 20 MHz (with sample drops possible above ~16 Msps on many USB hosts) |
| RX gain | RF amp (0/+14 dB) + LNA (0–40 dB, 8 dB steps) + VGA (0–62 dB, 2 dB steps) |
| TX gain | RF amp (0/+14 dB) + IF (0–47 dB, 1 dB steps) |
| TX output power | ~10 dBm typical at low frequency; falls off toward 6 GHz to ~5 dBm |
| Duplex | Half — cannot RX and TX simultaneously |
| Antenna port | SMA female, RX/TX shared (external T/R switch) |
| Reference clock | 25 ppm TCXO (internal); external clock input available |
| Interface | USB 2.0 High-Speed (480 Mbps) |
| Firmware | Great Scott Gadgets HackRF firmware (open source) |

## Why 8-bit ADC

The MAX5864 is 8-bit at 20 Msps. Practical implications:

- **Dynamic range** is ~48 dB SFDR (spurious-free dynamic range) at
  best, less in practice. A strong nearby signal (>−20 dBm at the
  antenna) consumes most of the ADC range and reduces sensitivity to
  weak signals.
- **Quantization noise** floor is at roughly `−6·N ≈ −48 dBFS`. For
  weak-signal work, oversample and decimate (see
  `../dsp/reference.md#Sampling`) to spread quantization noise into
  a band you can filter away.
- **The Airspy R2 and RTL-SDR** are 12-bit and 8-bit respectively;
  the RTL-SDR is 8-bit but only 3.2 Msps, so the HackRF has ~6× the
  bandwidth at the same bit depth. LimeSDR (12-bit, 30.72 Msps) and
  USRP B200 (12-bit, 61.44 Msps) beat the HackRF on dynamic range
  and rate.

## Why half-duplex

The T/R switch is a physical SPDT (single-pole double-throw) switch,
not two separate front ends. Switching between RX and TX takes
milliseconds and requires firmware coordination. Consequence: this
MCP's action model has separate `capture_iq` and `transmit_iq` verbs;
they cannot be interleaved sample-by-sample.

## PortaPack H2 / H4

Third-party (ShareBrained) accessory that adds:

- 2.8" LCD + directional pad + rotary encoder
- Battery
- Micro-SD slot for capture storage
- Mayhem firmware — a rich standalone SDR UI

Runs alongside the HackRF as a self-contained portable unit. Out of
scope for this MCP; documented here for completeness.

## Firmware update

```bash
# macOS:
hackrf_spiflash -w $(brew --prefix)/share/hackrf/firmware-bin/hackrf_one_usb.bin

# Ubuntu (path varies by package):
hackrf_spiflash -w /usr/share/hackrf/firmware-bin/hackrf_one_usb.bin
```

Unplug and replug after write. `hackrf_info` should report the new
version.

## External clock discipline

The 25 ppm TCXO is fine for most work but insufficient for GPS-locked
timing or long-baseline observations. GPSDO discipline via the
external clock input drops the effective ppm to whatever the GPSDO
delivers (typically <1e-9).

## Adjacent SDRs, for comparison

Full comparison in `../records/sdr_hardware.json` (once authored).
Quick pointers:

- **RTL-SDR v3 / v4** — RX-only, ~0.5–1.7 GHz (v3 with direct sampling
  hack for HF), 8-bit, ~3.2 Msps. Cheap, ubiquitous, great starter.
- **Airspy R2** — RX-only, 24 MHz – 1.8 GHz, 12-bit, 10 Msps. Better
  dynamic range than HackRF in that range.
- **LimeSDR (Mini/USB/XTRX)** — full-duplex, 100 kHz – 3.8 GHz,
  12-bit, up to 61 Msps. More expensive; better for high-throughput
  or full-duplex work.
- **USRP B200/B210** — full-duplex, 70 MHz – 6 GHz, 12-bit, 61.44
  Msps. Reference-quality; expensive.
- **KrakenSDR** — 5-channel RTL-SDR array for direction finding.
- **PlutoSDR (ADALM-Pluto)** — full-duplex, 325 MHz – 3.8 GHz (unlocked
  70 MHz – 6 GHz), 12-bit, 61 Msps. Learning-focused.
