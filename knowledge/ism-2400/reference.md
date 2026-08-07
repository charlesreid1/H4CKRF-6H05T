# ism-2400/reference.md — 2.4 GHz ISM

The single busiest license-free RF band on the planet. Bluetooth,
WiFi, Zigbee, most drone control links, wireless keyboards, microwave
ovens, and dozens of proprietary telemetry links all share these
83.5 MHz of spectrum.

## Band boundaries

| Property | Value |
|---|---|
| Nominal band | 2400–2483.5 MHz |
| Regulatory frame (US) | 47 CFR §15.247 / §15.249 |
| Regulatory frame (EU) | ETSI EN 300 328 |
| Region | Universal |
| Amateur overlap (US) | 13 cm amateur 2300–2450 MHz (partial) |
| Max EIRP (§15.247) | 30 dBm (1 W), plus antenna-gain rules |
| Max EIRP (§15.249) | 10 dBm (10 mW) |

Cross-record: `records/bands.json:band-ism-2400`.

## Denizens

- **WiFi 2.4 GHz (802.11 b/g/n/ax).** 14 channels of 22 MHz each,
  overlapping. Channels 1/6/11 are the non-overlapping "safe" trio in
  the Americas.
- **Bluetooth Classic + BLE.** 79 channels of 1 MHz (Classic) or 40
  channels of 2 MHz (BLE). FHSS across the band.
- **Zigbee / 802.15.4.** 16 channels of 5 MHz spacing (channels 11–26
  in 802.15.4 numbering).
- **RC drone links.** 2.4 GHz FHSS is dominant for hobbyist drones
  (DJI, FrSky, ExpressLRS). Video downlinks (analog FPV, DJI-O3) are
  also common.
- **Cordless phones (older).** DECT 6.0 uses 1.9 GHz, but pre-DECT
  and some Asian models operate at 2.4.
- **Microwave ovens.** ~2.45 GHz. Notably, they leak.

## Typical PHY summary

- **WiFi:** OFDM at 20/40/80 MHz. Wide, flat brick on a waterfall.
- **BT Classic:** GFSK 1 Mbaud, BT product 0.5. FHSS 1600 hops/s.
- **BLE:** GFSK 1 Msym/s (some variants at 2 Msym/s). Advertising
  channels 37/38/39 at 2.402/2.426/2.480 MHz.
- **Zigbee:** OQPSK 250 kbps (2.4 GHz PHY). 32-chip DSSS spreading.
- **Analog FPV video:** Wide FM analog video ~10 MHz occupied.

## Capture recipe

```
sweep_spectrum(start_freq_hz=2_400_000_000,
               end_freq_hz=2_483_500_000,
               dwell_s=2.0)

# BLE advertising channel isolation:
capture_iq(target_freq_hz=2_426_000_000,  # BLE ch 38
           sample_rate_hz=4_000_000,
           duration_s=1.0)

# Zigbee channel 15:
capture_iq(target_freq_hz=2_425_000_000,
           sample_rate_hz=8_000_000,
           duration_s=1.0)
```

## HackRF limitations at 2.4 GHz

- **8-bit ADC dynamic range is punishing here.** A nearby WiFi router
  will consume most of your ADC range and mask everything else.
- **20 Msps ceiling is barely enough for 802.11 20 MHz channels.**
  For full WiFi decode use a wider-BW SDR (LimeSDR, USRP B200).
- **Bluetooth Classic timing is tight.** 1600 hops/s across 79
  channels means each hop dwells ~625 μs; observing more than a
  fraction of a Bluetooth session requires channel-hopping in
  software.

## WiFi handoff

The WiFi side of this band is much better served by
**[P1N3NUT5](https://github.com/charlesreid1/P1N3NUT5)** (the WiFi
sibling repo). H4CKRF can:

- **Sweep** to confirm activity.
- **Observe** individual OFDM bursts (without decoding — a real WiFi
  receiver needs channel synchronization).
- **Recognize** WiFi vs Zigbee vs Bluetooth on a waterfall.

For decoding WiFi frames use `airodump-ng` / `hcxdumptool` / a real
monitor-mode adapter.

## Regulatory notes

- **Not BLOCKED** in the RiskAssessor. Compliance is the operator's
  responsibility.
- **The band is shared** — you're always sharing with WiFi and BT.
  High-power TX in this band interferes with the operator's own home
  network.

## Cross-references

- `knowledge/zigbee-802154/` — 802.15.4 PHY + MAC
- `knowledge/modulation/` — GFSK, OFDM, DSSS
- `knowledge/regulatory/` — Part 15 §15.247
