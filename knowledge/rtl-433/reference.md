# rtl-433/reference.md — the CLI surface

## Input formats

- **Live rtl-sdr:** the default. `-f <freq>` and `-s <sample_rate>`.
- **File input:** `-r capture.cs8` (or .cs16, .cu8, .cf32). Auto-detects
  format by extension.
- **Sample rate:** default 250 kHz for file input matches most rtl-sdr
  captures; for HackRF captures (typically 2 Msps), pass `-s 2000000`.

## Decoder selector

- `-R <n>` — enable only decoder n. Repeat to enable multiple.
- `-R -<n>` — disable decoder n.
- `-G` — enable all disabled-by-default decoders (worth trying if the
  default set finds nothing).

## Analyzer mode

- `-A` — dump pulse-code data for reverse engineering. Emits pulse
  widths + gaps in a form that reveals PWM / PPM / Manchester timing.

## Output formats

- **Default:** human-readable one-line summaries.
- `-F json` — one JSON object per decoded packet.
- `-F mqtt://host/topic` — publish to MQTT.
- `-F kv` — key-value pairs.
- `-F syslog:host:port` — syslog UDP.
- `-M level=N` — meta-info level (frequency, RSSI, SNR).

## Frequency / band strategy

- Default center: 433.92 MHz (EU ISM). Change with `-f`.
- Multi-frequency scan: `-f 315M -f 433M -f 868M -f 915M` (rotates every
  hop period).
- **For a HackRF capture, you must decimate first** — rtl_433 expects
  ~250-1024 ksps typical, and a 2 Msps HackRF capture wastes throughput.
  Use `sox` or a numpy resampler to bring it down to 250 or 1024 ksps.

## Top-20 built-in decoders (the ones you meet at a con)

- Acurite 592TXR / 606TX / 609TXC / 986 / 5n1
- Fine Offset WH1080 / WH24 / WH31 / WH51
- Oregon Scientific THGR / THN132 / RGR / WGR
- LaCrosse TX / TX141TH / TX35DTH
- Ambient Weather F007TH
- LightwaveRF (UK)
- Nexus temperature/humidity
- TPMS Schrader / Continental / Toyota / Ford
- Chamberlain / LiftMaster garage
- Nexa power switches (EU 433 MHz)
- Kerui / Vetrics burglar-alarm sensors

The full list: `rtl_433 -R help`.

## Citations

- rtl_433 GitHub (merbanan/rtl_433).
- RTL-SDR blog write-ups of the catalog.
