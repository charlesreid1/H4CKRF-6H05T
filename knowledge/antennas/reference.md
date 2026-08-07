# antennas/reference.md — the antenna zoo

## The formula

Wavelength `λ = c / f`. For an antenna to be efficient it must be an
integer fraction of λ (or an integer multiple).

- **Quarter-wave monopole:** `λ/4 = 75 / f_MHz` metres.
  - 315 MHz → 23.8 cm
  - 433 MHz → 17.3 cm
  - 915 MHz → 8.2 cm
  - 1090 MHz (ADS-B) → 6.9 cm
  - 2400 MHz → 3.1 cm
- **Half-wave dipole:** `λ/2 = 150 / f_MHz`, split into two `λ/4`
  elements.

Monopoles need a **ground plane** — a metal surface >= `λ/4` in
extent below the antenna. Dipoles don't.

## Gain quick reference

| Antenna | Typical gain (dBi) | Notes |
|---------|---------------------|-------|
| Isotropic (reference) | 0 | theoretical only |
| λ/4 monopole (over infinite ground) | 5.2 | practical: 2-3 |
| λ/2 dipole | 2.15 | omni in the H-plane |
| Discone | 1-3 | omni, wideband |
| Log-periodic (LPDA) | 6-9 | directional, wideband |
| Yagi (5 elements) | 8-10 | directional, narrowband |
| Biquad (2.4 GHz) | 10-12 | directional |
| Patch (microstrip) | 6-9 | can be circular polarization |
| Helical (axial) | 10-18 | circular polarization |
| Big dish | 20-50 | very directional, GHz+ |

## VSWR + S11

- **VSWR (Voltage Standing Wave Ratio):** ratio of forward to reflected
  RF voltage. 1.0 = perfect match, no reflection. > 2.0 = poor match,
  some TX power reflected back into the amplifier (bad — can damage
  the amp).
- **S11 (return loss):** the same measurement in dB.
  `S11_dB = 20 · log10((VSWR - 1) / (VSWR + 1))`.
  - VSWR 1.0 → S11 = -∞ dB (perfect).
  - VSWR 1.5 → S11 = -14 dB (good).
  - VSWR 2.0 → S11 = -9.5 dB (marginal).
  - VSWR 3.0 → S11 = -6 dB (poor).

**Measure with a VNA** (NanoVNA is <$50 and works from 50 kHz to
1.5 GHz).

## Feedline loss

Every metre of coax at UHF drops some fraction of a dB. For RG-58
at 433 MHz: ~0.5 dB/m. For LMR-400 at 1.5 GHz: ~0.2 dB/m.

- Short pigtails (<0.5 m) between HackRF and antenna are ideal.
- Long runs at 1.5+ GHz benefit from LMR-400 or hardline coax.

## HackRF-adjacent kit options

| Kit | Frequency range | Best for | Cost |
|-----|-----------------|----------|------|
| ANT500 (stock HackRF) | 75-1000 MHz | general VHF/UHF | included |
| RTL-SDR blog v3 telescoping | 100-1700 MHz | portable ADS-B, POCSAG | $30 |
| Diamond X50 discone | 50-1300 MHz | fixed base station | $80 |
| DIY biquad | 2400 MHz | 2.4 GHz direction finding | $10 in parts |
| DIY Yagi (1090 MHz) | narrow @ 1090 | ADS-B DX | $15 in parts |
| Patch (1575 MHz) | narrow @ 1575 | GPS RX | $30 |

## Polarization

- **Vertical:** most VHF/UHF land-mobile is vertical (feels intuitive
  for mobile antennas).
- **Horizontal:** most amateur SSB HF operators use horizontal wire
  antennas; also FM broadcast is often circular polarization biased
  horizontal.
- **Circular (RHCP/LHCP):** most GNSS satellites transmit RHCP.
  Iridium is LHCP.

Cross-polarization loss is ~20 dB, so it matters when you're near
the signal's marginal range.

## Match to target

- **433 MHz keyfob RX:** ANT500 or half-wave dipole. Anywhere >2 m
  from a metal object.
- **1090 MHz ADS-B RX:** a properly-tuned λ/4 monopole, or a DIY
  Yagi/collinear if you want DX.
- **868 MHz LoRa RX:** ANT500 or a dedicated 868 dipole.
- **2.4 GHz observation:** biquad if directional, telescoping whip
  otherwise.
- **GPS L1 (RX-only):** you need an active patch with an LNA — passive
  antennas rarely work at 1575 MHz.

## Citations

- Proakis & Salehi ch. 3.
- ARRL Antenna Handbook (canonical antenna reference).
- RTL-SDR blog antenna reviews.
