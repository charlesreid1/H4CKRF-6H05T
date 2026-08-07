# urh/walkthrough.md — captured keyfob → bits in under 5 minutes

The canonical URH workflow — the one most operators reach for first.

## Steps

1. **File → Open** — load your `capture.cs8` (or drag & drop).
2. **Signal pane** — URH auto-detects modulation and symbol rate.
   Sanity-check both:
   - Envelope collapsing between symbols → OOK. ✓ if matches.
   - Two spectral lobes → 2FSK.
3. **Manually set carrier** if the auto-detect got it wrong — click
   on the spectrogram at the actual carrier peak.
4. **Analysis pane** — right-click a message → "Decoding" → try:
   - **Manchester (IEEE)** — most 315/433 MHz keyfobs.
   - **Manchester (G.E. Thomas)** — sometimes needed with inverted
     polarity.
   - **PWM (short=0, long=1)** — Chamberlain legacy.
5. **Diff button** — compare 2-3 consecutive presses:
   - **All identical:** fixed-code keyfob.
   - **Last N bits increment by 1:** rolling-code (counter visible).
   - **Scrambled unpredictably:** cryptographic rolling — no easy replay.
6. **Export bits** — right-click a message → "Copy" or export the
   bit string.

## When to go beyond

- **URH exports a `.cs8` for transmit** — use the operator's
  `transmit_iq` MCP call (with a grant + through the safety funnel).
- **URH can't decode?** Try `rtl_433 -A capture.cs8` — it runs an
  exhaustive brute-force across ~250 known device types.
- **Still nothing?** Reach for `inspectrum` for a precision cursor,
  then hand-write a numpy decoder from what you measure.

## Common gotchas

- **Symbol rate off by 2×:** URH sometimes picks half the actual
  symbol rate on Manchester-encoded streams. Bit-stream will look
  like "011001101001..." rather than the true "010101...". Manually
  double it and re-decode.
- **Polarity inverted:** Some Manchester conventions are inverted.
  Try both.
- **Preamble length:** URH's default assumes 8-bit preamble; some
  vendors ship 4-bit or 16-bit. Adjust in message pattern.
- **File is too long:** URH loads the entire file into RAM. For
  captures >2 GB, decimate first with a numpy script.
