# gqrx-cubicsdr-sdrpp/reference.md — the GUI receiver zoo

## gqrx

- **Backend:** GNU Radio + gr-osmosdr.
- **Platforms:** Linux, macOS, BSD.
- **Features:** waterfall + FFT + audio demod (AM/FM/SSB/CW), AGC,
  DC removal, RDS decode, bookmarks, remote control via TCP.
- **Sample-rate driver:** HackRF's supported set (2/4/8/10/20 Msps).
- **File save:** raw IQ recording to `.wav` (float32 or int16) or via
  a GNU Radio flowgraph tap.

## CubicSDR

- **Backend:** LiquidDSP + SoapySDR.
- **Platforms:** Linux, macOS, Windows.
- **Features:** waterfall + FFT + multi-modem (multiple concurrent
  demodulators pinned to different frequencies), bookmarking,
  drag-to-zoom.
- **Notable:** the multi-modem view is unique to CubicSDR — good for
  monitoring several trunk voice channels at once.

## SDR++

- **Backend:** custom, SoapySDR-based.
- **Platforms:** Linux, macOS, Windows, Android.
- **Features:** modern plugin architecture; DSD++ plugin for DMR/P25;
  DX Cluster overlay for HF DXing; scanner mode.
- **Notable:** actively developed as of 2026, fastest-moving of the
  three.

## SDR#

- **Backend:** custom .NET.
- **Platforms:** Windows only, closed-source.
- **Mentioned for completeness.** Not recommended for reproducible
  work.

## Choosing between them

| Constraint | Pick |
|-----------|------|
| Linux/BSD, want GNU Radio underneath | gqrx |
| macOS or Windows, want cross-platform | CubicSDR or SDR++ |
| Want multiple demods at once | CubicSDR |
| Want a modern plugin ecosystem | SDR++ |
| Just want to listen to broadcast FM | any |

## What the assistant should recommend

- For live monitoring of a signal the operator hasn't captured yet:
  gqrx / CubicSDR / SDR++.
- For post-capture analysis of a saved IQ: URH, inspectrum, GNU Radio,
  or `analyze_iq_*` MCP verbs.

## Citations

- gqrx GitHub (csete/gqrx).
- CubicSDR GitHub (cjcliffe/CubicSDR).
- SDR++ GitHub (AlexandreRouma/SDRPlusPlus).
