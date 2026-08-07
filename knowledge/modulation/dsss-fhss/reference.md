# dsss-fhss/reference.md — direct-sequence and frequency-hopping

## DSSS — Direct-Sequence Spread Spectrum

Each data bit is multiplied by a fast pseudo-noise (PN) **chip sequence**;
the resulting waveform occupies `chip_rate` Hz of bandwidth. The
receiver correlates against the same PN to despread and recover the
bit.

- **Processing gain:** `10 · log10(chip_rate / bit_rate)` dB. For GPS
  L1 C/A this is `10·log10(1.023 MHz / 50 bps) ≈ 43 dB` — that's how
  a 20 W satellite at GEO produces a signal below the ambient noise
  floor at the ground.
- **Chip sequences:** Gold codes (GPS), Barker-7/11/13 (older WiFi
  802.11b), maximum-length sequences (M-sequences) in various
  research systems.
- **Under-modulation:** BPSK is the classic (Voyager, GPS L1 C/A).
  QPSK doubles capacity (GPS L1 P(Y), P5).

### GPS L1 C/A specifics

- Carrier: 1575.42 MHz.
- Chip rate: 1.023 MHz.
- Data rate: 50 bps.
- Chip sequence: 1023-chip Gold code, unique per satellite (PRN 1-32).
- Modulation: BPSK.

**TX blocked** at the safety gate — GPS spoofing is illegal.

### 802.11b (DSSS mode)

- Barker-11 chip sequence, 11 Mchip/s, 1 Mbps DBPSK / 2 Mbps DQPSK.
- CCK (complementary code keying) at 5.5/11 Mbps uses different chips.

## FHSS — Frequency-Hopping Spread Spectrum

The carrier jumps between predefined channels on a schedule known to
both TX and RX. Each dwell is a short burst; the schedule may be
pseudo-random.

- **Bluetooth Classic:** 79 channels × 1 MHz, 1600 hops/s (625 μs dwell),
  GFSK-1M or DPSK.
- **BLE (post-connection):** 37 data channels × 2 MHz, 7.5 ms - 4 s
  hop interval (variable per connection).
- **Older industrial ISM:** narrowband FSK hopping across a 900 MHz
  ISM sub-band.

### Bluetooth Classic hop pattern

Deterministic — a function of the master's Bluetooth Device Address
and CLK. Following the hop pattern requires knowing (or brute-forcing)
the BD_ADDR clock offset. Ubertooth's `ubertooth-scan` does this;
HackRF is a poor fit because 1600 hops/s means only ~625 μs to retune,
and HackRF's retune latency is ~ms.

## When to reach for what

| System | HackRF fit | Better tool |
|--------|-----------|-------------|
| GPS L1 (RX) | difficult — 20 MHz Nyquist required | dedicated GNSS receiver |
| 802.11b (observe) | possible with heavy decimation | 802.11 monitor mode |
| Bluetooth Classic | not viable (hop rate) | Ubertooth |
| BLE (observe adv) | possible with 3-channel scan | Ubertooth, Sniffle, WHAD |
| Zigbee 2.4 GHz | possible per-channel | ATUSB, Whsniff |
| Wideband FHSS ISM | possible with sweep + record | GNU Radio flowgraph |

## Citations

- Proakis & Salehi ch. 12 — spread spectrum.
- IEEE 802.15.1 (Bluetooth), Bluetooth Core Spec (BLE).
- IS-GPS-200 (GPS interface spec).
- IEEE 802.11 clauses 15-18 (DSSS PHY variants).
