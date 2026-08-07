# urh/reference.md — the four panes

## Signal (waveform + FFT)

- **Waveform view:** the raw IQ envelope over time. Cursor drag to
  measure symbol duration.
- **FFT view:** spectrum snapshot; drag a frequency selection to
  identify the carrier and estimate bandwidth.
- **Spectrogram view:** waterfall; drag a rectangle to zoom-in-time.

URH auto-detects **modulation** (OOK/2FSK/PSK), **carrier frequency**,
and **symbol rate** with reasonable accuracy on clean captures. Trust
but verify — force it to specific values if the auto-detect is off.

## Analysis (parameters)

Once URH has bits, this pane shows:

- **Encoding:** try NRZ, Manchester (IEEE and Thomas), differential
  Manchester, PWM, PPM. Right-click a bit stream → "Decoding" to
  cycle through.
- **Bit blocks:** group into 8-bit bytes and inspect hex.
- **Message pattern:** URH can suggest a per-packet layout (preamble
  vs sync vs address vs payload vs CRC) by comparing multiple messages.
- **Diff between messages:** the "Diff" tab highlights bits that
  change press-to-press — the fastest way to spot a rolling counter.

## Generation (encode → IQ)

- **Craft a message** — type hex bytes, choose an encoding, and URH
  builds the modulated IQ.
- **Attach it to a device** — URH can drive HackRF directly (or read
  an IQ file, or emit a `.cs8` to disk).
- **Save the IQ** and hand it to the operator's `transmit_iq` MCP call
  (subject to a grant + the safety funnel).

## Simulator (attack scenarios)

Sequences of RX/TX actions triggered by observed patterns — useful
for demonstrating protocol behavior in a controlled lab. The MCP does
not shell out here; the operator runs this themselves.

## File formats

Reads and writes:

- `.complex` — URH's native complex64.
- `.cs8`, `.cs16` — HackRF/Lime native.
- `.cf32` — GNU Radio default.
- `.wav` — SDR#/HDSDR variants.
- SigMF paired files (.sigmf-meta + .sigmf-data).

## When URH is not enough

- **Complex framing with FEC** — URH cannot un-scramble/whiten or do
  Viterbi. Reach for GNU Radio.
- **High symbol rates (>1 Mbaud)** — URH's GUI struggles with very
  fast streams; batch offline instead.
- **Non-trivial modulation classes** — OFDM, LoRa CSS. URH does not
  handle these.

## Citations

- URH GitHub (jopohl/urh).
- Pohl & Noack, "Universal Radio Hacker" (USENIX WOOT 2018).
