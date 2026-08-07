# dsss-fhss/recognition.md — spot on a waterfall

## DSSS

- **Wide, low-power pedestal.** Energy is spread over the chip rate,
  so the per-Hz power is low. Often *below* the noise floor for a
  small SDR — you see nothing until you know what to correlate.
- **Constant PSD across the band.** No distinguishing lobes or humps.
- **Long steady bursts** — one packet may be tens of ms without any
  visible substructure.
- **Peak-to-average envelope:** ~0 dB. Roughly constant.

Practically, DSSS is *invisible* on a spectrogram unless SNR is high.
When you can see it, look for a broad flat elevation over the noise
floor.

## FHSS

- **Discrete peppered spikes** on a waterfall — each spike is one hop's
  dwell time.
- **Bluetooth Classic:** 79 tiny 1 MHz spikes evenly spaced across
  2.402-2.480 GHz, each ~625 μs long. A busy piconet paints the whole
  2.4 GHz band with faint dots.
- **BLE (post-connection):** 37 spots across 2.402-2.480 GHz (avoiding
  the three advertising channels), longer dwell (7.5 ms - 4 s).
- **Legacy 900 MHz FHSS:** ~50 channels each ~200 kHz wide, hops
  irregularly.

## Confusables

- **DSSS vs a noise floor lift from AGC:** verify by turning down the
  LNA — a genuine DSSS signal stays flat; AGC lift moves with your
  gain.
- **FHSS vs many independent narrowband sources:** individual FHSS
  hops repeat on a schedule; independent sources don't. Look for
  regularity.
- **802.11b DSSS vs OFDM 802.11a/g/n:** DSSS at 802.11b has a
  ~22 MHz-wide pedestal with subtle sub-lobes; OFDM is a crisp flat
  brick with hard edges.

## What to do next

For any DSSS system where the chip sequence is public (GPS, 802.11b
Barker) you *can* correlate in numpy — expensive, but possible. For
proprietary DSSS, the receiver must know the code; without it,
you can only detect that *something is there*.

For FHSS, the practical target is Bluetooth Classic and BLE, and the
right tool is Ubertooth (or a dedicated BLE sniffer like Sniffle /
WHAD). HackRF is documented as "recognizes the band" — not "sniffs
Bluetooth."
