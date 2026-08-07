# signal-classification — the flag is the modulation name

The puzzle hands you an IQ file. The correct classification (e.g.
`GFSK`, `OFDM`, `LoRa-SF9-BW125`, `pi/4-DQPSK`) is the flag.

## Signature

The whole puzzle is signal classification. There's nothing to decode
past identifying what it is.

## Decode workflow

1. `analyze_iq_modulation(iq_path)` — the MCP's first-pass classifier.
   Returns family + confidence.
2. Cross-check with visual inspection:
   - **Constant envelope?** → PSK/FSK/CSS/OFDM(marginal).
   - **Envelope varies?** → AM/ASK/OOK/QAM.
   - **Spectral shape:** raised-cosine hump (PSK/QAM), twin lobes
     (2FSK), single soft hump (GFSK/MSK/GMSK), flat brick (OFDM),
     diagonal streaks (LoRa CSS), low-PSD pedestal (DSSS).
3. Verify with `records/modulations.json` and
   `records/known_signals.json`.
4. Cross-reference with the frequency: if the file is at 1090 MHz,
   the answer is PPM (Mode S). If at 137.100 MHz with a Meteor-M pass,
   the answer is QPSK.

## Common answers

- **OOK** — AM with 100% depth. Envelope collapses between symbols.
- **2FSK** — two spectral lobes. Constant envelope.
- **GFSK** — single blurred hump. Constant envelope. BLE, Bluetooth
  Classic.
- **GMSK** — MSK + Gaussian filtering. AIS uses BT=0.4.
- **BPSK/QPSK/8PSK/16-QAM** — RRC-shaped hump; distinguish by
  constellation.
- **OFDM** — flat brick.
- **CSS (LoRa)** — diagonal streaks; report SF and BW as part of the
  classification.
- **DSSS** — wide, low-PSD pedestal.
- **FHSS** — discrete peppered spikes.
- **π/4-DQPSK** — TETRA specific; constellation rotates by π/4
  between symbols.

## Sanity checks

- **`analyze_iq_modulation` returned "unknown":** try lower SNR
  cleanup — decimate, apply matched filter, retry.
- **Envelope + spectrum disagree:** clip/quantization in the capture
  may be hiding the true envelope. Recapture at lower gain.
- **Multiple candidates fit:** the more specific answer usually wins
  (`GFSK BT=0.5` beats `FSK`).

## What flag format to expect

- Simple string: `GFSK`, `OFDM`, `LoRa SF9 BW125`, `pi/4-DQPSK`.
- Sometimes with parameters: `GFSK,BT=0.5,rate=1M`.
- Puzzles may use canonical names; err toward the record `id`s in
  `modulations.json` if unsure.

## Cross-references

- `../modulation/reference.md` — the at-a-glance table
- `../modulation/*/recognition.md` — per-family waterfall triage
- `../records/modulations.json`, `records/known_signals.json`
- `../iq-analysis/reference.md` — the classifier heuristics
