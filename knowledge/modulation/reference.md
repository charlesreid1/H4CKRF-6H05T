# modulation/reference.md — at-a-glance table

The umbrella. Numeric properties per family — bandwidth vs symbol rate,
spectral signature, canonical use case, canonical demod pipeline. Full
records live in `../records/modulations.json`.

## Analog families

| Family | Bandwidth | Spectral signature | Canonical use | Demod pipeline |
|--------|-----------|--------------------|-------------|----------------|
| AM (DSB-LC) | 2 × audio bw | Central carrier + two symmetric sidebands with mirrored audio | Broadcast MW (530–1710 kHz), airband voice | `np.abs(x)` envelope detector |
| AM (DSB-SC) | 2 × audio bw | Two symmetric sidebands, no carrier | Legacy | Costas loop / synchronous detector |
| SSB (USB/LSB) | 1 × audio bw | One sideband only | Amateur HF voice, marine SSB | Frequency-shift + LPF |
| FM (narrowband) | ~15 kHz | Constant envelope, energy concentrated | Public safety VHF/UHF voice | `np.diff(unwrap(angle(x)))` |
| FM (wideband) | ~200 kHz | Constant envelope, energy spread by high deviation | Broadcast FM (88–108 MHz) | Same, plus deemphasis + stereo demux |

## Digital families

| Family | Symbol shape | Bandwidth vs symbol rate | Spectral signature | Canonical use |
|--------|--------------|-------------------------|--------------------|--------------|
| ASK-N | Amplitude, N levels | ~1.2 × Rs | Sinc-shaped spectrum, DC energy | Optical, some RFID |
| OOK | Amplitude, 2 levels (on/off) | ~1.2 × Rs | Sinc-shaped spectrum, gaps during "off" | 315/433 MHz keyfobs, garage doors, weather stations |
| 2FSK | Freq, 2 tones | ~2 × (deviation + Rs/2) | Two lobes at ±deviation | POCSAG, some keyfobs, Bluetooth Classic (as GFSK) |
| 4FSK | Freq, 4 tones | Broader | Four discrete lobes | FLEX 6400, DMR |
| GFSK | Gaussian-shaped FSK | Compressed vs plain FSK | Softer lobes | Bluetooth Classic (BT≈0.5), BLE (BT≈0.5), Sigfox uplink |
| MSK | Freq, h=0.5, continuous phase | ~1.2 × Rs | Compact single lobe | GSM (as GMSK) |
| GMSK | Gaussian MSK | Compressed further | Softer lobe | GSM downlink (BT≈0.3), AIS (BT≈0.4) |
| BPSK | Phase, 2 states | ~1.4 × Rs (RRC α=0.35) | Sinc-with-RRC | Deep-space, LoRa preamble |
| QPSK | Phase, 4 states | Same as BPSK | Compact | Satellite downlinks, DVB-S |
| 8PSK | Phase, 8 states | Same as QPSK | Compact | Satellite (higher throughput) |
| 16-QAM | Amp+phase, 16 pts | ~1.4 × Rs | Compact | Cellular, WiFi |
| 64/256-QAM | Amp+phase, dense | Same | Compact | LTE, WiFi 6 |
| OFDM | Many parallel narrow subcarriers | Wide, flat brick | Flat pedestal | WiFi, LTE downlink, DVB-T, 5G |
| CSS (chirp) | Frequency sweep across BW | 125/250/500 kHz per channel | Chirp streak on waterfall | LoRa |
| DSSS | BPSK spread by chip code | Chip rate × ~2 | Wideband, low PSD | GPS L1 C/A, older WiFi (802.11b) |
| FHSS | Frequency-hop over channel set | Instantaneous bw × dwell | Constellation of hops on waterfall | Bluetooth Classic (1600 hops/s), older WiFi |

## Cross-cutting properties

- **Constant envelope.** FM/FSK/GFSK/MSK/GMSK/PSK all keep `|x|`
  roughly constant. Handy: envelope isn't information, so class-C
  amplifiers work. Recognizable: `np.abs(x)` shows a nearly-flat
  line.
- **Amplitude-carrying.** AM/ASK/OOK/QAM all use amplitude. Envelope
  IS information. Class-A/AB amplifiers required for undistorted TX.
- **Constant phase (each symbol).** PSK/QAM discretize phase; FSK/FM
  vary phase continuously.

## Modulation index (for FSK)

`h = 2 · deviation / symbol_rate`

- `h = 0.5` → MSK (minimum bandwidth for coherent detection)
- `h ≈ 0.35` → GMSK for GSM
- `h ≈ 0.32` → BLE
- `h = 1.0` → "wideband" 2FSK (POCSAG classic)
- `h > 2` → deep FSK, easy on the demod but wide

## Roll-off / RRC α (for PSK/QAM)

- `α = 0.0` → Nyquist minimum, brutal ringing in time domain
- `α = 0.20` → LTE downlink
- `α = 0.35` → DVB-S, common default
- `α = 0.50` → some legacy links

Occupied bandwidth ≈ `(1 + α) · symbol_rate`.
