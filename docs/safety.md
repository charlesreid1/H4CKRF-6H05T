# Safety Policy & Frequency Reference

**This document is the source of truth for `frequency_policy.py` and `risk_assessor.py`.**
Every band, every citation, every rule those modules enforce is transcribed from this document.
Implementation is transcription, not judgment.

---

## Disclaimer

**HackRF One is a software-defined radio capable of transmitting on frequencies from
1 MHz to 6 GHz.** This software gates commands through a deterministic risk assessor,
but it cannot guarantee legal compliance. The operator (you) is responsible for:

1. Knowing and following all applicable laws in your jurisdiction.
2. Verifying that any transmission is authorized before approving it.
3. Understanding that the AI model is a statistical text generator, not an RF engineer or a lawyer.

**If you transmit on a frequency you are not authorized to use, you are liable for the
consequences, regardless of what this software or its AI backend told you.**

---

## Blocked Bands — Absolute Prohibitions

These frequency ranges are **BLOCKED for all actions** (RX and TX alike in some cases,
always for TX). The `frequency_policy.py` module encodes these as `BLOCKED_BANDS`.

### Aviation Safety-of-Life Bands

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **ADS-B / SSR / TCAS** | 1087–1093 MHz (1090 ± 3 MHz) | 47 CFR §87.131–147; ICAO Annex 10 Vol IV | ADS-B (1090 MHz), SSR, and TCAS/ACAS share this frequency. All civilian airliners broadcast position and receive collision-avoidance data here. Interference is a direct threat to flight safety. |
| **Aviation VHF Voice** | 118.000–137.000 MHz | 47 CFR §87.171–173; ICAO Annex 10 Vol V | Civil aviation voice communications (AM, 25 kHz and 8.33 kHz channels). Includes air traffic control, tower, ground, approach/departure, and emergency (121.5 MHz guard). |
| **VHF Guard (Emergency)** | 121.400–121.600 MHz (121.5 ± 100 kHz) | ICAO Annex 10 Vol V | International aeronautical emergency frequency. Military uses 243.0 MHz (UHF guard, harmonic of 121.5). |

### GNSS / Satellite Navigation Bands

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **GPS L1** | 1559–1591 MHz (1575.42 MHz center) | ITU RR Article 5 (RNSS allocation); 47 CFR Part 87 | GPS C/A code, P(Y) code, and modernized L1C. Civilian receivers worldwide depend on this signal. |
| **GPS L2** | 1215–1240 MHz (1227.60 MHz center) | ITU RR; 47 CFR Part 87 | GPS L2C and P(Y) code. Augments L1 for dual-frequency receivers. |
| **GPS L5** | 1164–1189 MHz (1176.45 MHz center) | ITU RR | Safety-of-life signal for aviation. Newer satellites. |
| **GLONASS G1** | 1592.9525–1610.485 MHz | ITU RR | Russian GNSS constellation G1 band. |
| **GLONASS G2** | 1237.8275–1254.4275 MHz | ITU RR | Russian GNSS constellation G2 band. |
| **Galileo E1** | 1559–1591 MHz | ITU RR | European GNSS (shares GPS L1). |
| **Galileo E6** | 1260–1300 MHz | ITU RR | European GNSS (commercial service). |
| **BeiDou B1** | 1559.052–1591.788 MHz | ITU RR | Chinese GNSS. |

### Maritime Distress & Safety

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **VHF Ch 16 (Distress)** | 156.7625–156.8375 MHz (156.8 ± 37.5 kHz) | 47 CFR §80.369; ITU RR Appendix 18 | International maritime distress, safety, and calling frequency. Monitored by all coast stations and SOLAS vessels. |
| **VHF Ch 70 (DSC)** | 156.525 MHz | ITU RR Appendix 18 | Digital Selective Calling — automated distress alerting. |
| **MF/HF Distress** | 2182 kHz, 4125 kHz, 6215 kHz, 8291 kHz, 12290 kHz, 16420 kHz | ITU RR | Maritime distress and safety HF frequencies. HackRF's minimum is 1 MHz, so 2182 kHz is within range. |

### Cellular Downlink Bands (US)

Transmitting on cellular downlink interferes with mobile devices receiving base-station signals.
All are **BLOCKED for TX**.

| Band | Uplink (UE → Tower) | Downlink (Tower → UE) | FCC Rule Part | Carrier Usage |
|------|---------------------|----------------------|---------------|---------------|
| **Band 2** (PCS 1900) | 1850–1910 MHz | **1930–1990 MHz** | 47 CFR Part 24E | AT&T, Verizon, T-Mobile |
| **Band 4** (AWS) | 1710–1755 MHz | **2110–2155 MHz** | 47 CFR Part 27 | AT&T, Verizon, T-Mobile |
| **Band 5** (Cell 850) | 824–849 MHz | **869–894 MHz** | 47 CFR Part 22H | AT&T, US Cellular |
| **Band 12** (700 Lower) | 699–716 MHz | **729–746 MHz** | 47 CFR Part 27 | AT&T, T-Mobile |
| **Band 13** (700 Upper C) | 777–787 MHz | **746–756 MHz** | 47 CFR Part 27 | Verizon (primary) |
| **Band 17** (700 Lower B/C) | 704–716 MHz | **734–746 MHz** | 47 CFR Part 27 | AT&T |

**Additional blocked downlink ranges** (not exhaustive; the frequency policy module encodes
the full set):

- **600 MHz band** (Band 71): downlink 617–652 MHz (T-Mobile)
- **2300 MHz band** (Band 30): downlink 2350–2360 MHz (AT&T)
- **2500 MHz band** (Band 41): 2496–2690 MHz (TDD — both directions blocked)
- **CBRS** (Band 48): 3550–3700 MHz (shared, but blocked for TX out of caution)

### Emergency Services

| Band | Frequency Range | Reason |
|------|----------------|--------|
| **Public Safety 700 MHz** | 758–769 MHz, 788–799 MHz (narrowband), 769–775 MHz, 799–805 MHz (broadband) | FirstNet and public safety LTE |
| **VHF Public Safety** | 150.8–156.2475 MHz, 157.1875–161.575 MHz | Police, fire, EMS VHF allocations (varies by locality) |
| **UHF Public Safety** | 453.0–454.0 MHz, 460.0–460.6375 MHz | Public safety UHF |
| **800 MHz Public Safety** | 806–809 MHz, 851–854 MHz (NPSPAC) | Public safety 800 MHz |

### Radio Astronomy & Passive Services

| Band | Frequency Range | Reason |
|------|----------------|--------|
| **Hydrogen line** | 1400–1427 MHz (1420.40575177 MHz center) | Protected passive band — radio astronomy. The 21 cm hydrogen line is one of the most important frequencies in radio astronomy. TX is prohibited internationally. |
| **Radio astronomy** | 406.1–410.0 MHz, 608–614 MHz, 1335–1350 MHz, 2690–2700 MHz, 4990–5000 MHz | ITU-R RA.769 protected radio astronomy bands. |

---

## ISM Bands — Permitted for Unlicensed Operation (FCC Part 15)

These bands are available for low-power unlicensed devices under FCC Part 15 rules.
The HackRF agent treats these as **default-allowed for RX; TX is MEDIUM-tier if within
band and legal power limits, HIGH-tier otherwise.**

| Band | Frequency Range | Applicable FCC Rule | Notes |
|------|----------------|---------------------|-------|
| **315 MHz** | 310–320 MHz (center 315 MHz) | 47 CFR §15.231 | Periodic transmitters only (keyfobs, garage doors, tire pressure sensors). Field strength limit: 6,041–6,417 µV/m at 3 m (fundamental). Transmission must be manually initiated and cease within 5 seconds. |
| **433 MHz ISM** | 433.05–434.79 MHz | 47 CFR §15.231 (US); ETSI EN 300 220 (EU, Region 1 ISM) | ISM Region 1 band. In the US, falls under §15.231's 260–470 MHz general periodic-transmitter rules. Much wider allowed operation in EU (433.05–434.79 MHz ISM). LoRa, Amateur radio secondary. |
| **902–928 MHz** | 902.000–928.000 MHz | 47 CFR §15.247 (FHSS/DSSS, up to 1 W conducted); §15.249 (narrowband, 50 mV/m @ 3 m) | The main US ISM band below 2.4 GHz. LoRa, Z-Wave, amateur radio (33 cm band, secondary). Amateur allocation is 902.000–928.000 MHz exactly. |
| **2.4 GHz** | 2400.0–2483.5 MHz | 47 CFR §15.247 (up to 1 W); §15.249 | Wi-Fi, Bluetooth, Zigbee, amateur (13 cm band 2300–2450 MHz, with 2400–2450 for satellite and broadband). |
| **5.8 GHz** | 5725.0–5875.0 MHz | 47 CFR §15.247; §15.249 | Upper ISM band. Wi-Fi 5 GHz (U-NII-3), some amateur operation. |

---

## Amateur Radio Allocations (47 CFR Part 97)

These are amateur (ham) bands that overlap with HackRF's frequency range.
Operating here requires a valid amateur radio license. **The HackRF agent cannot
substitute for a license — but these bands are not BLOCKED by default because
licensed operators may use them.** The risk is HIGH for TX in amateur bands
without explicit user grants.

| Band Name | Frequency Range | Notes |
|-----------|----------------|-------|
| **1.25 m** | 222–225 MHz | US-only amateur band. |
| **70 cm** | 420–450 MHz | Amateur primary. 433.00–435.00 MHz = auxiliary/repeater links. Shared with government radiolocation; amateur is secondary in some sub-bands. |
| **33 cm** | 902–928 MHz | Amateur secondary to ISM and government. ARRL band plan divides into weak-signal (902.0–903.4), mixed (903.4–909.0), broadband (909.0–927.0), repeater outputs (927.0–928.0). |
| **23 cm** | 1240–1300 MHz | Amateur primary. Overlaps with GPS L2 (1227.60 MHz). Amateurs must not interfere with RNSS. |
| **13 cm** | 2300–2450 MHz | Amateur secondary in 2300–2310; primary in 2390–2450 (but 2400–2450 overlaps ISM). 2310–2390 is non-amateur (Part 27 WCS). |

---

## Risk-Tier Ladder

This is the deterministic classification applied by `risk_assessor.py` to every command.
The LLM never assigns its own tier.

| Tier | Meaning | Criteria | Examples |
|------|---------|----------|----------|
| **LOW** | Auto-execute, no confirmation | Read-only, bounded duration, no disk write outside session dir | `get_device_info`, `sweep_spectrum` (RX, ≤2 s dwell), short `capture_iq` (≤5 s, to session path), `grant_list`, `audit_query` |
| **MEDIUM** | Single-key confirmation (Y/n) | Longer capture, higher gain, disk writes, TX in ISM bands within legal power | `capture_iq` >5 s, `transmit_iq` on 433.05–434.79 MHz with gain ≤ 30 dB, `decode_ook`, `read_iq_summary` |
| **HIGH** | Must type CONFIRM | TX anywhere non-trivial, high gain, long TX, TX outside ISM but not blocked, any TX without an active grant | `transmit_iq` with gain > 30 dB, TX on 315 MHz (higher power), TX on amateur bands, any `transmit_iq` above +30 dB total gain |
| **BLOCKED** | Refused, no appeal | Protected bands (see Blocked Bands table), illegal ranges, TX gain exceeds hardware maximum (47 dB) | TX on 1090 MHz, 1575 MHz, 156.8 MHz, cellular downlink, aviation voice, GPS bands, TX VGA gain > 47 dB |

### Gain Caps

HackRF One has three gain stages:

| Stage | Range | Step Size | Notes |
|-------|-------|-----------|-------|
| **RF Amp** | 0 or 14 dB | 14 dB | On/off. Enable for weak signals. |
| **LNA (RX)** | 0–40 dB | 8 dB | RX only. `lna_gain_db` clamped to {0, 8, 16, 24, 32, 40}. |
| **VGA (RX)** | 0–62 dB | 2 dB | RX baseband gain. |
| **VGA (TX)** | 0–47 dB | 1 dB | TX IF gain. **Capped at 47 dB by the risk assessor.** |

The `risk_assessor.py` caps `tx_vga_gain_db` at 47 dB (hardware maximum) and applies an
additional policy cap of 30 dB for MEDIUM-tier TX. Transmitting at >30 dB TX VGA gain
forces HIGH tier.

---

## References

- **FCC Part 15** (Radio Frequency Devices): [ecfr.gov — 47 CFR Part 15](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15)
  - §15.209 — General radiated emission limits
  - §15.231 — Periodic operation in the band 40.66–40.70 MHz and above 70 MHz
  - §15.247 — Operation within the bands 902–928 MHz, 2400–2483.5 MHz, and 5725–5850 MHz
  - §15.249 — Operation within the bands 902–928 MHz, 2400–2483.5 MHz, 5725–5875 MHz, and 24.0–24.25 GHz
- **FCC Part 87** (Aviation Services): [ecfr.gov — 47 CFR Part 87](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-87)
- **FCC Part 80** (Maritime Services): [ecfr.gov — 47 CFR Part 80](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-80)
- **FCC Part 97** (Amateur Radio Service): [ecfr.gov — 47 CFR Part 97](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97)
- **FCC Part 22** (Public Mobile Services): Cellular 850 MHz band
- **FCC Part 24** (Personal Communications Services): PCS 1900 MHz band
- **FCC Part 27** (Miscellaneous Wireless Communications Services): AWS, 700 MHz, 2300 MHz, 600 MHz bands
- **ARRL Band Plan**: [arrl.org/band-plan](https://www.arrl.org/band-plan)
- **ITU Radio Regulations**: [itu.int/pub/R-REG-RR](https://www.itu.int/pub/R-REG-RR)
- **ICAO Annex 10** (Aeronautical Telecommunications): Vol IV (Surveillance Radar), Vol V (Aeronautical Radio Frequency Spectrum Utilization)
- **HackRF One Hardware**: [greatscottgadgets.com/hackrf/one/](https://greatscottgadgets.com/hackrf/one/)
