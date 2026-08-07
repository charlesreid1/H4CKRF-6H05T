# ism-868-915/reference.md — EU 868 MHz / US 915 MHz LPWAN

The LPWAN sub-GHz playground: LoRaWAN, Sigfox, Z-Wave, various
proprietary telemetry. Region-split — the same protocol uses
different frequencies in different regions.

## Band boundaries

| Property | EU (Region 1) | US (Region 2) |
|---|---|---|
| Nominal band | 863–870 MHz | 902–928 MHz |
| Regulatory frame | ETSI EN 300 220 | 47 CFR §15.247/§15.249 |
| Sub-band structure | 4+ SRD sub-bands with per-band ERP + duty cycle | Contiguous with 26 MHz total |
| ERP limit | 25 mW–500 mW per sub-band | 30 dBm (§15.247), 20 dBm (§15.249) |
| Duty cycle | 0.1%, 1%, 10%, or unlimited per sub-band | No duty cycle limit |

Cross-records: `records/bands.json:band-ism-868`, `band-ism-902-928`.

## Sub-band details (EU)

| Sub-band | Range | ERP | Duty cycle | Common use |
|---|---|---|---|---|
| a | 868.0–868.6 MHz | 25 mW | 1% | Wireless mic, LoRa uplink |
| b | 868.7–869.2 MHz | 25 mW | 0.1% | Alarms, telemetry |
| c | 869.4–869.65 MHz | 500 mW | 10% | High-power alarms |
| d | 869.7–870.0 MHz | 5 mW | Unlimited | Continuous data links |

## LPWAN protocols

- **LoRaWAN.** CSS (chirp spread spectrum). EU868 (868.1/868.3/868.5
  MHz for uplinks, 869.525 MHz for downlink RX2), US915 (64 uplink
  channels 902.3–914.9 MHz, 500 kHz channels + 8 downlink), AU915,
  AS923. Spreading factors SF7–SF12; bandwidths 125/250/500 kHz.
- **Sigfox.** Ultra-narrowband DBPSK, 100 Hz uplink, 600 bps downlink.
  EU 868.13 MHz, US 902.2 MHz.
- **Z-Wave.** GFSK. EU 868.42 MHz, US 908.42 MHz. Mesh IoT.
- **KNX-RF.** BFSK at 868.3 MHz. Smart home wired-to-wireless bridge.
- **Wireless M-Bus (wM-Bus).** Utility meter reading. Modes S/T/C/N
  cover different sub-bands and modulations.
- **Proprietary telemetry.** SCADA links, industrial sensor networks.

## Typical PHY summary

- **LoRa CSS:** identifiable by chirp streaks on a waterfall (see
  `../modulation/recognition.md`).
- **Sigfox:** invisible on any but the narrowest FFT; 100 Hz signals
  don't show up in a 2 MHz-wide sweep.
- **Z-Wave/wM-Bus:** narrow GFSK, ~40 kHz occupied bandwidth,
  9600–100 000 bps.

## Capture recipe

```
sweep_spectrum(start_freq_hz=902_000_000, end_freq_hz=928_000_000,
               dwell_s=1.0)      # US 915

sweep_spectrum(start_freq_hz=863_000_000, end_freq_hz=870_000_000,
               dwell_s=1.0)      # EU 868

# LoRa: capture at chirp-BW granularity (125 kHz is standard)
capture_iq(target_freq_hz=915_000_000,
           sample_rate_hz=2_000_000,
           duration_s=5.0)

# Recognize the chirp on the spectrogram:
analyze_iq_spectrogram(iq_path, sample_rate_hz=2_000_000, fft_size=256)
# Diagonal peak_freqs_hz across time → LoRa.
```

## Regulatory notes

- **EU 868 and US 915 do not overlap.** A device sold in one region
  cannot legally operate in the other without recertification.
- **This MCP does not decode LoRa payloads.** The corpus and
  `analyze_iq_spectrogram` can recognize CSS but a full LoRa decoder
  is out of scope for now. Use `gr-lora_sdr` or `sdrangel` externally
  and hand the resulting bits back.

## Cross-references

- `knowledge/lora/` — LoRa PHY in detail
- `knowledge/modulation/` — CSS recognition
- `knowledge/regulatory/` — Part 15 / EN 300 220 details
