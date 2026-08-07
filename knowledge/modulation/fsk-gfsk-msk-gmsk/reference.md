# fsk-gfsk-msk-gmsk/reference.md — the frequency-keying family

## Modulation index

The single most important number:

```
h = 2 · Δf / Rs
```

- `h ≥ 1.0` → **wideband 2FSK** (POCSAG at h≈7.5, some 315/433 MHz
  keyfobs at h~1-2).
- `h = 0.5` → **MSK**. Minimum spacing for coherent detection.
- `h < 0.5` combined with Gaussian filtering → **GFSK / GMSK**.

## 2FSK

Two frequencies (`±Δf` around fc, symbol rate `Rs`). Constant envelope.

- **Spectral shape:** two lobes at `±Δf`. If `h > 1`, lobes are distinct;
  if `h < 0.5`, they blur into a single hump.
- **Canonical uses:** POCSAG 512/1200/2400 baud (Δf=4.5 kHz, h≈7.5 at
  1200), FLEX (4FSK variant), some sub-GHz keyfobs at 315/433 MHz.

## 4FSK

Four frequencies (`±3Δf, ±Δf`). Doubles bit rate at the same symbol
rate.

- **Canonical uses:** FLEX 3200/6400 bps, DMR (4FSK at 4800 sym/s),
  P25 Phase 1 (C4FM is 4FSK), NXDN 4800/9600.

## GFSK (Gaussian FSK)

FSK with a Gaussian pulse-shaping filter applied to the frequency
modulation. The `BT` product (bandwidth × symbol period) is the shaping
parameter.

- **`BT ≈ 0.5`:** Bluetooth Classic (1 Mbaud), BLE (1 Mbaud with h≈0.32,
  or 2 Mbaud with h≈0.5), Sigfox uplink downlink.
- **`BT ≈ 0.3`:** legacy Zigbee 900 MHz variants; some LPWANs.

Gaussian filtering tightens the spectrum vs plain FSK but introduces
inter-symbol interference — the receiver's matched filter compensates.

## MSK (Minimum Shift Keying)

FSK with `h = 0.5` exactly. Frequency changes are continuous-phase
(no phase jumps between symbols), so the spectrum is more compact than
plain 2FSK.

- **Spectral shape:** single main lobe ~1.5·Rs wide.
- **Canonical uses:** deep-space, ACARS (older).

## GMSK (Gaussian MSK)

MSK with Gaussian pulse shaping.

- **`BT = 0.3`:** GSM downlink (270.833 kbaud, TX BLOCKED for HackRF).
- **`BT = 0.4`:** AIS (9.6 kbaud).
- **`BT = 0.5`:** BLE 1M advertising uses GFSK-like shaping close to
  this; some CC1101 vendor modes.

## Demod methods

- **Instantaneous frequency (best for h ≥ 1):**
  `inst_f = np.diff(np.unwrap(np.angle(x))) * fs / (2·π)`, slice around
  the midpoint. Non-coherent, robust, cheap.
- **Quadrature demodulator (best for h < 1):**
  `y = x[1:] * np.conj(x[:-1])`; take `np.angle(y)`, slice. Same idea
  as instantaneous frequency but avoids the unwrap step.
- **Matched filter + slicer:** RRC-shaped for GFSK/GMSK; correlator
  banks against the two (or four) expected frequency responses.

## Citations

- Proakis & Salehi ch. 4 — angle modulation.
- ITU-R M.584-2 (POCSAG).
- ETSI EN 300 392 (TETRA π/4-DQPSK, not 4FSK — cross-reference only).
- Bluetooth Core Specification (BLE PHY).
