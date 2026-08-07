# iq-analysis — recognition

Quick visual identification of common signals from a waterfall or
`read_iq_summary` output.

## Shape → suspect

| Waterfall shape | Suspect |
|-----------------|---------|
| Single narrow spike, seconds long | fixed carrier, unmodulated LO, or CW jammer |
| Narrow spike, 30-100 ms bursts, 3-5 repeats | keyfob (315/433 MHz OOK) |
| Two closely-spaced peaks (~5-50 kHz apart), sustained | 2FSK — POCSAG, some paging |
| Wide flat "brick" spanning MHz | OFDM — WiFi, LTE, DVB-T |
| Dozens of narrow spikes hopping | FHSS — Bluetooth (1600 hops/s), some LoRaWAN |
| Diagonal streaks, sloped, repeating | LoRa CSS chirp |
| Comma-shaped sync burst, then codewords | POCSAG batch header |
| Vertical line at DC (center of capture) | LO leakage / DC spike — not signal |
| Regular flat wideband ~1 MHz around DC | HackRF ADC noise floor at high gain |

## Occupancy heuristics

- `< 1%` — quiet band, nothing there or your gain is too low
- `1-5%` — one or a few narrow signals (typical keyfob / weather-station
  capture)
- `5-20%` — active band, multiple signals or a wider-bandwidth service
- `> 30%` — wideband signal (OFDM, LoRa at low SF) or gain saturation

## SNR heuristics (peak minus noise floor)

- `> 40 dB` — plenty of margin; decoder should sail through
- `20-40 dB` — decodable with good clock recovery
- `10-20 dB` — expect bit errors; retry captures if the decoder fails
- `< 10 dB` — buried; increase gain, move antenna, or retune

## Peak frequency

Interpret `peak_freq_hz` relative to what you asked for:

- If `peak_freq_hz == center_freq_hz`, you're looking at the DC spike,
  not the signal. Recapture with `target_freq_hz` instead of
  `center_freq_hz` so the tuner offsets the LO by `sample_rate/4`.
- If `peak_freq_hz` is at the edge of the capture band, the signal is
  outside your passband — retune with a wider `sample_rate_hz` or a
  different `target_freq_hz`.

## Symbol-rate cheatsheet by band

| Band | Typical symbol rate | Likely PHY |
|------|--------------------|-----------|
| 315 / 433 MHz | 1-4 kbps | OOK keyfob / weather / TPMS |
| 315 / 433 MHz | 9.6-40 kbps | GFSK LPWAN |
| 868 / 915 MHz | 1.2-38.4 kbps | LoRa / Z-Wave / GFSK |
| 1090 MHz | 1 Mbps chip | ADS-B Mode S PPM |
| 1.6 GHz | 1200 baud | Iridium bursts (short) |
| 2.4 GHz | 1 Msym | BLE GFSK |
| 2.4 GHz | 250 kbps | Zigbee 802.15.4 OQPSK |

## What is definitely NOT what you think it is

Common false positives:

- **DC spike is not a signal.** The strong bin at `center_freq_hz`
  after RX-tuning is LO leakage, always.
- **Adjacent-channel spillover is not a signal.** If you see mirror
  images equidistant from the peak, that's IQ imbalance, not a real
  second transmitter.
- **The noise floor is not zero.** HackRF at 8-bit ADC has a
  ~48 dB usable dynamic range — you cannot see anything more than
  ~48 dB below the strongest bin.

## Cross-references

- `knowledge/sdr-fundamentals/` for the DC-spike-avoidance rule
- `knowledge/hackrf-hardware/` for the 8-bit ADC dynamic-range constraint
- `knowledge/modulation/recognition.md` for per-family spectrogram
  signatures
