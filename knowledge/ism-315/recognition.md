# ism-315/recognition.md — what to expect when sweeping 310–320 MHz

## Waterfall archetypes

**Short, bursty narrow spike at 315.0 or 314.9 MHz**
Probably a keyfob press or a TPMS ping. Bursts last 30–100 ms.
Repetition: keyfobs send 3–5 bursts per press with 20 ms gaps; TPMS
transmitters spool up on wheel motion (every ~90 s at highway speed)
or on gross pressure change.

**Recurring quiet pings at 315.0 MHz, roughly 60–90 seconds apart**
Almost certainly TPMS from a nearby parked car whose tires still have
residual motion signature. Each burst is ~10 ms.

**A single sinc-shaped narrow lobe at 315.0 that never modulates**
Someone left a keyfob pressed against a pocket. Or it's a beacon.
Uncommon.

**Two burst positions at 314.85 and 315.15**
Some Ford / GM keyfob systems dual-channel to increase reliability.
Not FSK per se — two separate OOK bursts on distinct sub-frequencies.

## Time-domain envelope

- **Square-topped bursts, sharp on/off** → OOK. Nearly every §15.231
  device.
- **Envelope stays flat but center frequency shifts** → 2FSK. Rare in
  this band, but some higher-security keyfobs use it.
- **Constant sinusoid** → beacon or stuck transmitter.

## Symbol-rate hints

`analyze_iq_symbols` should return:

- ~2000 Hz for classic Chamberlain / Genie garage openers
- ~2000–4000 Hz for automobile keyfobs (Ford, GM, Chrysler)
- ~9600 Hz for some newer TPMS chipsets (Schrader ASK-9600)

If the estimator returns something wildly outside 500–10 000, either
the burst got clipped or the capture is picking up a harmonic of a
different band.

## Common pitfalls

- **DC spike lands on your signal.** Always use `target_freq_hz`, not
  `center_freq_hz`, when tuning to 315.0.
- **Nearby FM broadcast bleed-through.** 315 MHz is a long way from
  88–108 MHz but strong local FM can still contaminate the front end
  if the HackRF's LNA gain is high. Drop LNA to 16 dB for a survey
  before pushing to 40 dB.
- **False bursts from LED bulbs.** Some cheap LED drivers radiate
  broadband noise around 300 MHz. Move the antenna a few meters to
  test.

## What "the flag is here" looks like in CTF

- The frequency IS the flag → obscure sub-band allocation (e.g.,
  312.115 MHz was a specific Motorola paging channel in the 90s).
- The bitstream IS the flag → decode Manchester at ~2 kbps and
  look for printable ASCII or a familiar CRC.
- The pattern of bursts IS the flag → count bursts per press,
  measure inter-burst gap, compare to Chamberlain Security+ 2.0
  specifics.
