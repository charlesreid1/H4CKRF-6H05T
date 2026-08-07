# gnu-radio-primer/reference.md — the block model

## The three surfaces

- **GRC** (GNU Radio Companion) — drag-and-drop GUI over a YAML flow
  description. Renders to a runnable Python file.
- **Python API** — instantiate `gr.top_block()`, add source/sink/
  filter blocks, `.connect()` them, `.run()`. This is what GRC emits.
- **C++ block dev** — for custom DSP. `gr_modtool` scaffolds a
  new out-of-tree (OOT) module.

## The block model

Every block has:

- **Ports:** stream (typed float32/complex64/int8/…) or message (PMTs).
- **Buffers:** input/output ring buffers; blocks are scheduled by the
  scheduler when work is available.
- **`work()`:** the callback that consumes N input samples and produces
  M output samples.

**Tag streams:** an out-of-band way to attach metadata (e.g. "burst
starts here") to specific sample positions. Used by e.g. burst
detectors feeding a symbol synchronizer.

**Message ports + PMTs:** the way blocks pass structured data (dicts,
lists, atoms) — used by e.g. a header parser telling a payload decoder
"expect 240 bytes."

## Canonical block library

| Category | Block | What it does |
|----------|-------|--------------|
| Source | `osmocom Source` | HackRF, RTL-SDR, USRP, LimeSDR, PlutoSDR |
| Source | `File Source` | reads .cs8/.cs16/.cf32 |
| Sink | `File Sink` | writes .cs8/.cs16/.cf32 |
| Sink | `osmocom Sink` | TX to HackRF/USRP/LimeSDR |
| Sink | `QT GUI Sink` | live waterfall + FFT |
| Filter | `Low Pass Filter` | FIR LPF (magic-generated tap sizes) |
| Filter | `Rational Resampler` | polyphase P/Q resampler |
| Demod | `Quadrature Demod` | inst. frequency for FSK/FM |
| Demod | `Costas Loop` | carrier recovery for M-PSK |
| Demod | `Symbol Sync` | Gardner/M&M/Zero-Crossing timing |
| Encoder | `Packet Encoder` | preamble + payload + CRC |
| Utility | `Throttle` | rate-limit non-hardware sources (dev only) |

## Getting real work done

Three flowgraphs everyone should be able to draw:

1. **Broadcast FM RX** — `osmocom Source` → `Rational Resampler` →
   `Quadrature Demod` → `Rational Resampler` → `WAV File Sink`.
2. **OOK keyfob analyzer** — `File Source (cs8)` → `Complex to Mag` →
   `Threshold` → `File Sink (binary)` + `QT GUI Time Sink` for
   visualization.
3. **POCSAG pipeline** — `osmocom Source` → narrow LPF → `Quadrature
   Demod` → resample to 22050 Hz → `WAV File Sink` → pipe to
   `multimon-ng -a POCSAG1200`.

## Out-of-tree modules worth knowing

- **gr-osmosdr** — universal SDR driver.
- **gr-air-modes** — ADS-B Mode S (historical, still works).
- **gr-ais** — AIS.
- **gr-iridium** — Iridium downlink.
- **gr-lora_sdr** — LoRa PHY (EPFL fork; modern).
- **gr-pager** — POCSAG/FLEX.
- **gr-satellites** — CCSDS TM decoders for cubesats.

## Citations

- GNU Radio wiki (wiki.gnuradio.org) — the canonical reference.
- Ossmann SDR lecture series — GNU Radio-flavored throughout.
