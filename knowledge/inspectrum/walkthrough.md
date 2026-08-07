# inspectrum/walkthrough.md — measure symbol rate in 30 seconds

## Steps

1. **Open** — `inspectrum capture.cs8` (or File → Open in the GUI).
   Set the sample rate in the launch args if the filename doesn't
   encode it (`-r 2000000`).
2. **Locate a burst** — scroll the waterfall to find a clean burst
   (visible envelope, no ringing).
3. **Zoom in** — mouse wheel + drag until you can see individual
   symbol edges.
4. **Add a symbol-rate cursor** — right-click on the spectrogram →
   "Add symbol cursor." Drag between two visible symbol transitions.
5. **Read the number** — the cursor overlay shows the interval in
   samples and translates to symbols/second at your sample rate.

## What you get

- **Exact symbol rate** — better than URH's auto-detect on noisy
  or short bursts.
- **Confirmed carrier offset** — a frequency cursor on the peak vs
  the center frequency.
- **Approximate bandwidth** — width of the visible spectral energy at
  a chosen dB down from the peak (e.g. 3 dB, 20 dB).

## After inspectrum

- Feed the measured symbol rate into `rtl_433 -A -s <symbol_rate> -f
  <freq> capture.cs8` for a decoder brute-force.
- Or write a targeted numpy decoder with the known symbol rate.
- Or feed the values into URH to override its guesses.
