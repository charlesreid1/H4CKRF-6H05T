# psk-qam/reference.md — phase-shift keying and quadrature amplitude modulation

## Constellations

- **BPSK:** 2 points at 0 and π rad. `1 bit/symbol`.
- **QPSK:** 4 points at π/4, 3π/4, 5π/4, 7π/4. `2 bits/symbol`.
- **8PSK:** 8 points spaced π/4 apart. `3 bits/symbol`.
- **16-QAM:** 4×4 grid. `4 bits/symbol`.
- **64-QAM:** 8×8 grid. `6 bits/symbol`.
- **256-QAM:** 16×16 grid. `8 bits/symbol`.

## Pulse shaping

Real receivers use root-raised-cosine (RRC) pulse shaping to limit
inter-symbol interference (ISI):

```
h_RRC(t, α) = ... (see Proakis §9.2)
```

- **α = 0** → Nyquist minimum bandwidth (`Rs`), infinite time-domain
  ringing.
- **α = 0.20** → LTE downlink.
- **α = 0.25** → DVB-S2.
- **α = 0.35** → DVB-S, common default in flowgraph tutorials.

Occupied bandwidth ≈ `(1 + α) · Rs`.

## Carrier recovery

Every PSK/QAM receiver needs to lock a local oscillator to the incoming
signal's carrier phase. **Costas loop** is the classic solution — an
M-power Costas loop handles M-ary PSK. Squaring loops work for BPSK.

For QAM, the constellation isn't rotation-symmetric so blind carrier
recovery is harder; decision-directed loops help once you're close.

## Timing recovery

**Gardner** (2 samples/symbol, carrier-independent) is common in GNU
Radio's `symbol_sync` block for BPSK/QPSK. **Mueller-Müller** (1 sample/
symbol, decision-directed) is more efficient once you've locked
carrier.

## Differential variants

**DBPSK / DQPSK:** encode data in the *phase difference* between
consecutive symbols. Advantage: no absolute carrier phase needed at
the receiver. Cost: ~3 dB SNR penalty.

**π/4-DQPSK:** QPSK rotated by π/4 between symbols — used in TETRA
(18 ksym/s), some legacy cellular. Avoids zero-crossings, so amplifiers
can run in more efficient classes.

## Canonical uses

| Family | Where you meet it |
|--------|-------------------|
| BPSK | GOES HRIT (927 ksym/s), LoRa preamble sync, deep space |
| QPSK | DVB-S, most satellite downlinks, LTE downlink (subset of subcarriers) |
| 8PSK | DVB-S2, higher-throughput satellite links |
| 16-QAM | LTE downlink at medium SNR, WiFi 802.11n MCS 3-6 |
| 64-QAM | LTE downlink at high SNR, WiFi 802.11n MCS 7 |
| 256-QAM | LTE-A / WiFi 6 high-SNR modes |
| DQPSK | TETRA (π/4-DQPSK), some legacy standards |

## Citations

- Proakis & Salehi ch. 4-5.
- Rice, *Digital Communications: A Discrete-Time Approach* — carrier/
  timing recovery, matched filtering.
- ETSI EN 300 392 (TETRA).
