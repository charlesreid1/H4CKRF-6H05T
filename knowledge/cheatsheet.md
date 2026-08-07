# cheatsheet — the load-bearing reference card

The single densest page in the corpus. Every entry is a one-liner an
operator can memorize or paste into a terminal. For depth, follow the
cross-references to the per-topic files.

## HackRF One at a glance

- **Frequency:** 1 MHz — 6 GHz.
- **ADC/DAC:** 8-bit interleaved.
- **Sample rates:** 2, 4, 8, 10, 20 Msps supported.
- **USB:** 2.0, half-duplex TX/RX (not simultaneous).
- **Chipset:** MAX2837 + RFFC5072 + MAX5864.
- **Clock:** 25 ppm TCXO stock; external clock input for GPSDO.
- **SFDR:** ~48 dB.

## Bands you'll meet

- **ISM (RX unrestricted; TX per Part 15 / EN 300 220):**
  315 MHz (US), 433.05-434.79 MHz (EU), 902-928 MHz (US),
  863-870 MHz (EU), 2400-2483.5 MHz.
- **Amateur:** 144-148 MHz (2m), 430-450 MHz (70cm) — license required.
- **BLOCKED for TX** in this MCP: ADS-B 1090 MHz; GPS L1 1575.42,
  L2 1227.60, L5 1176.45 MHz; airband 118-137 MHz; maritime distress
  156.7625-156.8375 MHz; cellular downlink; other emergency services.

## Modulation → demod recipe

| Modulation | Recipe |
|-----------|--------|
| AM (broadcast, airband) | `env = np.abs(x)` |
| FM (voice) | `np.diff(np.unwrap(np.angle(x))) * fs / (2*pi)` |
| OOK | `env = np.abs(x); threshold` |
| 2FSK | instantaneous frequency, slice around midpoint |
| GFSK / GMSK | quadrature demod, matched filter |
| BPSK | Costas + slice on `.real` |
| QPSK | Costas + quadrant classify |
| 16-QAM | Costas + nearest-neighbor slice |
| OFDM | out of scope — hand off to LTE/WiFi tools |
| LoRa CSS | dechirp + FFT + argmax → symbol index |

## Decoder recipe by symbol shape

| Symbol shape | Decoder | Verb |
|-------------|---------|------|
| Two levels, self-clocking | Manchester | `decode_manchester` |
| Two levels, no clock | NRZ | `decode_nrz` |
| Long/short pulses | PWM | `decode_pwm` |
| Fixed pulse, gap-encoded | PPM | `decode_ppm` |
| HDLC flag-delimited | NRZI + bit-stuff | `decode_ax25` |

## DSP formulas

- **Nyquist (real):** `f_max < fs / 2`.
- **Nyquist (IQ):** total bandwidth captured = fs.
- **FFT bin width:** `fs / N`.
- **Envelope:** `np.abs(x)`.
- **Instantaneous phase:** `np.angle(x)`.
- **Instantaneous frequency (Hz):**
  `np.diff(np.unwrap(np.angle(x))) * fs / (2*pi)`.
- **Downsample by K:** `scipy.signal.decimate(x, K)`.
- **Welch PSD:** `scipy.signal.welch(x, fs=fs, nperseg=4096)`.
- **DC spike removal:** tune with `target_freq_hz` offset, not
  `center_freq_hz`.

## IQ format quick reference

| Extension | Type | Where |
|-----------|------|-------|
| `.cs8` | int8 IQ | HackRF native |
| `.cu8` | uint8 IQ (biased ~127) | RTL-SDR native |
| `.cs16` | int16 IQ | LimeSDR / USRP |
| `.cf32` | float32 IQ | GNU Radio default |
| `.wav` | float32 or int16 IQ | SDR# / HDSDR |
| `.sigmf-data` + `.sigmf-meta` | any datatype + JSON sidecar | archival |

**Convert HackRF `.cs8` → complex64:**

```python
raw = np.fromfile(path, dtype=np.int8)
iq = (raw[::2] + 1j * raw[1::2]).astype(np.complex64) / 128.0
```

## Common signals at common frequencies

| Freq (MHz) | Signal | Modulation |
|-----------|--------|-----------|
| 27 | US CB | AM / SSB |
| 88-108 | FM broadcast | Wide FM |
| 118-137 | Airband voice | AM (BLOCKED TX) |
| 137 | NOAA APT | AM subcarrier on FM |
| 144-148 | 2m amateur | mixed |
| 145.8 | ISS voice | narrow FM |
| 152-174 | US paging + LMR | 2FSK / 4FSK |
| 156-162 | Marine VHF | narrow FM (Ch 16 BLOCKED) |
| 161.975/162.025 | AIS | GMSK |
| 315 | US keyfobs / TPMS | OOK Manchester |
| 400-470 | LMR (DMR / P25) | 4FSK / C4FM |
| 433.92 | EU ISM (keyfobs / weather / LoRa) | OOK / GFSK / CSS |
| 462-467 | GMRS / FRS | narrow FM |
| 863-870 | EU LoRaWAN + Sigfox | LoRa CSS / DBPSK |
| 902-928 | US LoRaWAN + Z-Wave | LoRa CSS / GFSK |
| 908.42 | Z-Wave US | GFSK |
| 1090 | ADS-B Mode S | PPM (BLOCKED TX) |
| 1575.42 | GPS L1 | BPSK-1 (BLOCKED TX) |
| 1616-1626 | Iridium | DQPSK TDMA |
| 1694 | GOES HRIT | BPSK |
| 2400-2483.5 | 2.4 GHz ISM (WiFi/BLE/Zigbee) | OFDM / GFSK / OQPSK |

## Antenna length (quarter-wave whip)

`length_cm = 7500 / freq_MHz`

| Frequency | Length |
|-----------|--------|
| 315 MHz | 23.8 cm |
| 433 MHz | 17.3 cm |
| 915 MHz | 8.2 cm |
| 1090 MHz | 6.9 cm |
| 2400 MHz | 3.1 cm |

## POCSAG at 1200 baud

- 2FSK, ±4.5 kHz deviation, 1200 baud.
- 32-bit codewords with BCH(31,21) + parity.
- Sync word `0x7CD215D8`.
- Batch = 1 sync + 8 frames of 2 codewords = 17 codewords.
- Decodable with `multimon-ng -a POCSAG1200` from a 22050 Hz WAV of
  the FM-discriminated audio.

## ADS-B Mode S

- 1090 MHz PPM, 1 Mbps chip rate.
- Long frame 112 bits (120 μs), short frame 56 bits (64 μs).
- CRC-24 with Mode S parity `0xFFF409`.
- **RX only.** Decode via `dump1090 --iq --iformat sc16` or `readsb`.
- ICAO24 in bits 8-31 of the frame.

## Manchester keyfob PHY (majority of 315/433 MHz keyfobs)

- OOK carrier, 2-4 kbps.
- Manchester-encoded (IEEE 802.3 or G.E. Thomas — try both).
- Packet: preamble (0xAA...) + sync + ID + counter + CRC.
- 3-5 repeats per press with short gaps.

## LoRa CSS

- Symbol duration: `T_sym = 2^SF / BW` seconds.
- Spreading factors 7-12; bandwidths 125, 250, 500 kHz.
- Preamble = 8 up-chirps; SFD = 2 down-chirps.
- Dechirp by multiplying with the conjugate down-chirp; FFT-per-symbol.

## Cross-references

- `dsp/` — DSP primer
- `modulation/` and its subtopics — per-family reference
- `records/known_signals.json` — the canonical signals table
- `records/bands.json`, `records/regulatory.json` — band + regulatory
  quick lookups
- `docs/ctf_playbook.md` — operator playbook
