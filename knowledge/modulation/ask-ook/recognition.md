# ask-ook/recognition.md — spot OOK on a waterfall

## Signature

- **Sharp on/off transitions:** the envelope snaps between "carrier
  present" and "carrier absent." Contrast against FSK (constant
  envelope) and QAM (multi-level envelope).
- **Sinc-lobe skirts:** OOK's spectrum is a `sinc²`. Poorly-filtered
  transmitters spread lobes across ±few × symbol rate; a well-designed
  transmitter shapes them with a raised-cosine.
- **Burst structure:** most keyfobs and TPMS senders retransmit the
  same packet 3-8 times per press with short gaps — a spectrogram row
  of ~50-100 ms bursts with ~20-50 ms gaps.
- **Manchester on top:** the AM envelope shows a clean 2×-symbol-rate
  transition pattern (visible in `np.abs(x)` at a high enough sample
  rate).

## Confusables

- **OOK vs 2FSK:** OOK's envelope collapses to near-zero during 0-bits;
  FSK's envelope is constant. `np.abs(x)` differentiates immediately.
- **OOK vs pulsed radar:** radar has huge peak-to-average envelopes but
  the pulses are ~µs wide and the PRF is regular; OOK is ~ms bit
  duration with irregular structure.
- **OOK vs a chirp burst (LoRa):** LoRa is constant-envelope on the
  waterfall; OOK has hard on/off gaps.

## Waterfall triage

If you see, on a 433.92 MHz spectrogram:

1. Bursts ~50 ms long, repeating 3-8x per press, ~30 kHz wide → **keyfob
   or garage door.** Almost certainly OOK/Manchester.
2. Short (~10-30 ms) bursts, single-shot per event → **weather station
   or TPMS.** OOK or 2FSK depending on vendor.
3. Long (~100 ms), single-shot, wider (~200 kHz) → probably not OOK;
   check for 2FSK or CSS.
