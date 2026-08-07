# satellite/reference.md — satellite downlinks the HackRF can hear

Weather sats, ham radio via ISS, Iridium, GNSS, and a few
odd-frequency classics. All are receive-only from the HackRF's
perspective (transmitting to a satellite is another matter entirely
— licensing + link budget + antenna are all extreme).

## NOAA APT (Automatic Picture Transmission)

Legacy analog weather imagery from NOAA-15/18/19.

- **Frequencies:** 137.100, 137.620, 137.9125 MHz (depending on
  which sat).
- **Modulation:** FM with a ~2400 Hz AM-subcarrier for image data.
- **Access:** Direct downlink; anyone can decode with a $30 antenna.
- **Deployment status:** NOAA-15/18/19 all past design life. NOAA-19
  active as of 2026 but expected to sunset. GOES HRIT is the
  replacement.
- **Popular decoders:** `noaa-apt`, `WXtoImg` (legacy), `SatDump`.

## GOES HRIT / EMWIN / DCS

Geostationary weather sat downlinks (much richer than APT).

- **Frequencies (GOES-16/18):** 1694.1 MHz (HRIT), 1692.7 MHz
  (EMWIN), various DCS frequencies.
- **Modulation:** QPSK, complex framing.
- **PHY:** ~1 Mbps HRIT with LDPC FEC.
- **Antenna:** Requires a 60+ cm dish pointed at GOES; a HackRF whip
  won't cut it.
- **Deployment status:** Active, growing.
- **Decoder:** `SatDump`.

## Iridium

Constellation of ~66 LEO sats providing satellite phone service.

- **Frequency band:** 1616–1626 MHz (uplink and downlink share).
- **Modulation:** QPSK, ~50 kbaud.
- **PHY:** L-band service link with proprietary framing.
- **Vulnerability:** Iridium's control channel is unencrypted; the
  Iridium Toolkit (`gr-iridium`) can decode broadcast channels.
- **Deployment status:** Active.

## ISS voice + APRS

Amateur radio via the International Space Station.

- **Voice:** 145.800 MHz downlink (FM).
- **APRS digipeat:** 145.825 MHz.
- **Deployment status:** Active, but voice contacts are rare;
  scheduled school contacts a few times a month.

## GPS L1 C/A code

The universal GNSS downlink.

- **Frequency:** 1575.42 MHz.
- **Modulation:** BPSK + DSSS with per-satellite Gold codes.
- **Deployment status:** Constellation is always active. **BLOCKED
  for TX** in the RiskAssessor.
- **Practical RX:** Requires -130 dBm sensitivity; even with a great
  antenna the HackRF's 8-bit ADC won't pull useful GPS. Use a
  dedicated GPS module.

## Numbers stations (HF, off-band for HackRF)

Shortwave numbers stations transmit spoken digit strings, believed to
be intelligence agency one-time-pad transmissions.

- **Frequencies:** Most below 30 MHz (out of HackRF's practical
  range).
- **Modulation:** Analog AM/USB voice.
- **Deployment status:** A dozen or so active as of 2026. UVB-76
  ("The Buzzer") on 4625 kHz is the most famous.
- **Access via HackRF:** Not directly — you need a HF upconverter or
  a separate HF receiver.

## Meteor-M LRPT

Russian polar-orbit weather sats (Meteor-M N2, N2-2, N2-3).

- **Frequency:** 137.100 MHz (some models on 137.9125).
- **Modulation:** QPSK 72 kbaud with LDPC.
- **Deployment status:** Active. Image quality far better than APT.
- **Decoder:** `SatDump`.

## Capture recipe (NOAA APT)

```
sweep_spectrum(start_freq_hz=137_000_000, end_freq_hz=138_000_000,
               dwell_s=1.0)
# During a pass, you'll see a wide FM signal on one of the
# 137 MHz APT frequencies.

capture_iq(target_freq_hz=137_912_500,
           sample_rate_hz=200_000,
           duration_s=900.0)  # 15-minute pass
```

Then hand the .iq to `noaa-apt` or `SatDump` externally. This MCP
doesn't currently ship a satellite-specific decoder.

## Cross-references

- `knowledge/regulatory/` — GPS L1 BLOCKED reasoning
- `records/bands.json:band-gps-l1`
