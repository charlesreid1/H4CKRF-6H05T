# fsk-gfsk-msk-gmsk/recognition.md — spot on a waterfall

## 2FSK (wide, h ≥ 1)

- **Two distinct spectral lobes** at ±Δf around the carrier.
- **Constant envelope** — `np.abs(x)` is flat.
- **Symbol edges: soft slope** in inst_f, not the hard on/off of OOK.
- **POCSAG at 1200 baud** looks like a ~9 kHz wide, ~500 ms long burst
  with a distinctive cadence.

## GFSK (h < 1, Gaussian-shaped)

- **Two lobes blurred into a single wider hump.** Sidelobes are much
  softer than plain 2FSK.
- **Constant envelope.**
- **Bluetooth Classic:** 1 Mbaud, 79 discrete channels each 1 MHz wide
  — appears as short bursts *hopping* across 2.402-2.480 GHz (see
  FHSS notes).
- **BLE advertising:** three channels only (2.402, 2.426, 2.480 GHz) —
  short bursts, each ~180-380 μs, ~2 MHz wide.

## MSK

- **Single compact main lobe**, ~1.2·Rs wide. No visible ±Δf shoulders.
- **Constant envelope.**
- Rare in the wild without Gaussian filtering — usually you're looking
  at GMSK.

## GMSK

- **Single hump, softer edges than MSK**, spectral efficiency higher.
- **AIS at 9.6 kbaud (BT=0.4):** ~25 kHz-wide bursts at 161.975 or
  162.025 MHz, ~30 ms long. Waterfall shows periodic clusters (SOTDMA).
- **GSM downlink (BT=0.3):** flat 200 kHz-wide slot at each ARFCN.
  HackRF can RX; TX is blocked at the safety gate.

## Confusables

- **2FSK vs GFSK:** examine the *sidelobe* shape. Plain FSK has ringing
  sidelobes; GFSK's sidelobes are quiet.
- **GFSK vs MSK:** GFSK typically has BT<0.5 and h<0.5; MSK has h=0.5
  exactly and no Gaussian shaping. Look at inst-frequency histogram —
  MSK is two sharp lines; GFSK is two blurred humps.
- **2FSK vs OOK:** envelope. OOK collapses to zero between symbols;
  FSK doesn't.
