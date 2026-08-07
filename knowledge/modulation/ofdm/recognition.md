# ofdm/recognition.md — spot OFDM on a waterfall

## Signature

- **Flat brick.** A wideband channel with uniform PSD from one edge
  to the other. Contrast against PSK/QAM (raised-cosine hump) or FSK
  (twin lobes).
- **Sharp edges.** Because the outer subcarriers are gated off, the
  spectrum has crisp corners rather than skirts.
- **Envelope non-constant.** OFDM has ~10 dB PAPR — `np.abs(x)` shows
  large amplitude variation despite the flat spectrum.
- **DC null.** A visible thin gap right at the tuned frequency inside
  the flat brick is the intentionally-nulled DC subcarrier.

## Confusables

- **OFDM vs DSSS:** DSSS is a wide, *low-PSD* pedestal (spread over
  chip rate); OFDM is wide with *nominal PSD* (data energy). At
  ADC-clipped SNRs both can look flat, but envelopes differ.
- **OFDM vs a wideband noise source:** OFDM has structure at the
  subcarrier level (visible on a fine-resolution FFT); noise doesn't.
- **OFDM vs LoRa CSS at 500 kHz BW:** LoRa is a diagonal chirp streak,
  not a flat brick.

## What the assistant should NOT do

- Attempt full frame decode. **The MCP corpus is explicit that OFDM
  decoding is out of scope** — WiFi is P1N3NUT5 territory, cellular
  is bibliography-only.
- Guess the subcarrier count from a spectrogram alone. Even
  distinguishing 20 MHz WiFi from 20 MHz LTE requires frame-level
  observation (WiFi has plainly visible preamble patterns; LTE has
  the CRS pilot every subframe).
