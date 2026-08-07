# ofdm/reference.md — OFDM primer

## The block diagram

```
data bits → QAM/PSK map → serial-to-parallel N streams
         → IFFT (size N) → parallel-to-serial → prepend cyclic prefix
         → DAC → upconvert → antenna
```

Reversed at the receiver: strip cyclic prefix → FFT → per-subcarrier
demod.

## Numbers

- **Subcarrier spacing (Δf):** `1 / T_useful` where T_useful is the
  IFFT integration time. E.g. LTE 15 kHz spacing → T_useful = 66.7 μs.
- **Cyclic prefix (CP):** guard interval prepended to each symbol,
  ~7-25% of T_useful, that absorbs multipath delay. CP length is
  a system-dependent constant.
- **Pilots:** a handful of subcarriers carry known symbols used for
  channel estimation; the rest carry data.
- **DC subcarrier:** typically nulled (or lightly modulated).
- **Guard subcarriers:** the outer few subcarriers on each side are
  nulled to give the analog filter a clean transition band.

## OFDM in the wild

| System | Subcarriers | Δf | CP | Channel BW |
|--------|-------------|----|----|-----------|
| WiFi 802.11a/g | 52 (48 data + 4 pilot) | 312.5 kHz | 800 ns | 20 MHz |
| WiFi 802.11n HT | 56 (52 data + 4 pilot) | 312.5 kHz | 400/800 ns | 20/40 MHz |
| LTE (normal CP) | 12 per RB, up to 1200 total | 15 kHz | 4.7 μs | 1.4-20 MHz |
| DVB-T | 6817 (8k mode) | 1.116 kHz | 7-224 μs | 8 MHz |
| DAB | 1536-3072 | 1 kHz | 246 μs | 1.536 MHz |
| 5G NR (numerology 0) | up to 3300 | 15 kHz | 4.7 μs | 5-100 MHz |
| 5G NR (numerology 1) | up to 3300 | 30 kHz | 2.35 μs | 10-200 MHz |

## OFDMA (multi-access variant)

The base station assigns different subcarriers to different users. LTE
uplink is SC-FDMA (a DFT-precoded variant); LTE downlink is plain
OFDMA. 5G NR extends the concept with flexible numerology.

## PAPR

The IFFT summing produces a Peak-to-Average Power Ratio problem:
individual OFDM symbols can have envelope peaks ~10 dB above average.
This is why LTE uplink uses DFT-precoded OFDM (SC-FDMA) — to lower PAPR
for handset amplifiers.

## Demod difficulty

OFDM is easy to *identify* (flat spectrum) but hard to *decode from
scratch* with a HackRF because:

- **Sample rate ceiling** — 20 Msps caps WiFi 20 MHz observations at
  Nyquist. LTE 10 MHz channels work; LTE 20 MHz needs decimation
  tricks.
- **PHY complexity** — channel estimation, coarse frame sync, CFO
  correction, per-subcarrier equalization, LDPC decoding.

Reach for `srsRAN` / `Open5GS` for LTE, `Aircrack-ng`-adjacent tools
for WiFi. **The MCP does not decode OFDM at frame level.**

## Citations

- Proakis & Salehi ch. 12 — OFDM.
- IEEE 802.11 (WiFi PHY).
- 3GPP TS 36.211 (LTE physical channels).
- 3GPP TS 38.211 (NR physical channels).
