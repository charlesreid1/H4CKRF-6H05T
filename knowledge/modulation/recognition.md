# modulation/recognition.md — how each family looks on a waterfall

The load-bearing file for triage. Pattern → likely family → next step.

## OOK / ASK-2

**Look:** A single narrow spectral lobe (sinc-shaped) with time-varying
amplitude. On a waterfall: bursts of energy separated by gaps. On a
time-domain envelope plot: a square-ish on/off pattern.

**Confusables:** Any pulsed narrowband signal (e.g. a very quiet 2FSK
where the frequency separation is smaller than your FFT bin width).

**Next step:** `read_iq_summary` to confirm burst structure;
`decode_manchester` with a symbol rate around 1–4 kbps for most
315/433 MHz keyfobs.

## 2FSK

**Look:** Two symmetric lobes around the carrier, each roughly `Rs/2`
wide. On a waterfall: two horizontal bands that alternate energy as
bits toggle. Constant envelope in the time domain (unlike OOK).

**Confusables:** Wideband 2FSK vs narrowband FM voice (both have two
lobes for a single tone, but FM voice has continuous audio, 2FSK has
discrete transitions).

**Next step:** Instantaneous frequency (`np.diff(np.unwrap(np.angle))`);
check that it discretizes to two values.

## GFSK

**Look:** Two soft-shouldered lobes (Gaussian filter has smoothed the
transitions). Narrower total occupied bandwidth than 2FSK at the same
symbol rate.

**Confusables:** 2FSK with a longer-tap RRC filter looks similar.
Bluetooth Classic (BT≈0.5) is the classic GFSK sighting at 2.4 GHz.

**Next step:** Look up the band in `../records/bands.json`; check
whether Bluetooth or another GFSK protocol is expected there.

## MSK / GMSK

**Look:** A single compact lobe, constant envelope. GMSK is even more
compact than plain MSK (Gaussian smoothing).

**Confusables:** Narrowband FM voice. The tell is the discrete symbol
transitions in the instantaneous frequency plot.

**Next step:** GSM downlink (900/1800/1900 MHz — BLOCKED for TX),
AIS at 161.975/162.025 MHz.

## PSK / QPSK / 8PSK

**Look:** A single lobe, RRC-shaped. Constant envelope (BPSK/QPSK
technically not — but close). Constellation diagram (I vs Q scatter)
shows 2/4/8 discrete points on a circle.

**Confusables:** Any RRC-shaped digital signal.

**Next step:** Downsample to 1 sample/symbol; plot `Q vs I`; count
constellation points.

## QAM

**Look:** RRC-shaped single lobe, non-constant envelope. Constellation
shows a regular grid (4×4 for 16-QAM, 8×8 for 64-QAM).

**Next step:** Same as PSK but expect a grid, not a circle.

## OFDM

**Look:** A wide, nearly-flat spectral brick. On a waterfall: solid
horizontal band. Time-domain envelope looks like noise (high PAPR).

**Confusables:** True noise. The tell: OFDM has a well-defined edge
where a filter cuts it off; noise doesn't.

**Next step:** WiFi (2.4/5/6 GHz), LTE downlink (many bands),
DVB-T (470–790 MHz). If cellular downlink → **BLOCKED for TX.**

## CSS (LoRa chirp)

**Look:** Diagonal streaks on a waterfall — the chirp sweeps up or
down across the channel bandwidth. Each symbol is one full chirp
period. Spreading factor determines the chirp duration.

**Confusables:** Nothing else looks like this. This is the most
distinctive digital modulation on a waterfall.

**Next step:** `../records/protocols.json` for LoRaWAN parameters
(SF7–SF12, 125/250/500 kHz BW). Analyze with a LoRa decoder (out of
scope for this MCP directly).

## FHSS

**Look:** A constellation of narrow spikes at different frequencies
over time; a waterfall shows a "peppered" pattern with each spike
lasting one hop dwell.

**Confusables:** Interference from a hopping neighbor.

**Next step:** Bluetooth Classic (1600 hops/s across 79 channels in
2.4 GHz) is the canonical sighting. Reception requires channel
hopping in software — beyond simple `capture_iq`.

## Continuous unmodulated carrier

**Look:** A single infinitely-narrow tone. Constant envelope, no
information.

**Confusables:** DC spike (which is at 0 Hz in complex baseband —
retune to check).

**Next step:** Beacon, calibration signal, or an untended TX. If it
carries no information, it isn't the flag by itself; it might be
part of a "the frequency IS the flag" puzzle.
