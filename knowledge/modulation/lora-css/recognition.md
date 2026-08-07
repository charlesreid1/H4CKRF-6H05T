# lora-css/recognition.md — spot LoRa on a waterfall

## Signature — unmistakable

- **Parallel diagonal streaks.** Each chirp sweeps from `-BW/2` to
  `+BW/2` (up-chirp) in one symbol period. On a spectrogram with
  time on the y-axis, they appear as diagonal lines whose slope is
  `BW / T_sym = 2^SF / BW`.
- **Constant envelope.** `np.abs(x)` is flat during the chirp.
- **8-symbol preamble** at the start — 8 diagonals all with the same
  starting frequency. The rest of the packet has diagonals with
  cyclic-shifted start points, so they *look* the same shape but
  start at different heights.
- **Ends with a down-chirp SFD** (start of frame delimiter) — one or
  two diagonals with *inverted* slope.

## Parameters from a spectrogram

- **Channel bandwidth (125/250/500 kHz):** width of one diagonal streak.
- **Symbol duration:** vertical (time) extent of one diagonal streak.
- **Spreading factor:** derive from `T_sym = 2^SF / BW`. If you measure
  T_sym = 8.192 ms and BW = 125 kHz, `2^SF = T_sym · BW = 1024 → SF=10`.

## Confusables

- **LoRa vs FMCW radar sweep:** FMCW radar chirps typically sweep at
  much higher rates (μs, MHz-wide) and *only* forward, not with an
  inverted-slope SFD.
- **LoRa vs a jamming sweep:** jamming sweeps rarely have the
  8-preamble + 2-SFD structure. Look for the preamble regularity.
- **LoRa at SF12 vs a slow FM ramp:** SF12 chirps last 32.8 ms at
  125 kHz — visually distinguishable from FM by their linearity and
  discrete restart points.

## What to do next

- Announce the SF, BW, and center frequency.
- Hand the file off to `gr-lora_sdr` or `sdrangel` (LoRa decoder built
  in).
- If it's LoRaWAN, note that decoding stops at the LoRa PHY frame —
  the MAC-layer payload is AES-128 encrypted.
