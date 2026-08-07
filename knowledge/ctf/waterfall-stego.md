# waterfall-stego — image or text hidden in the spectrogram

Some CTFs hide the flag by AM-modulating a carrier so its FFT bins
draw text, a QR code, or an image in the waterfall.

## The signature

- The spectrogram looks *too clean.* Bands of solid-color power with
  crisp edges that don't correspond to any known protocol.
- Vertical spacing of the bands looks arbitrary — not a Bluetooth
  hop pattern, not a POCSAG comb.
- Bright rectangles arranged in letters, digits, or a QR square.

## The workflow

1. **`analyze_iq_spectrogram`** with a large `fft_size` (2048-8192)
   and low overlap (0.25) so the picture is sharp.
2. Save the returned `peak_freqs_hz` + `peak_dbfs` arrays.
3. Reconstruct the image externally — every FFT slice is one column
   of pixels; the peak freq is the row where a bright pixel lives.
4. If the image is text, OCR it. If it's a QR, scan it.

The H4CKRF stack does not ship an image renderer for this. The
operator dumps the arrays to numpy / matplotlib to see the picture.

## Common variations

- **Multi-line text.** Multiple peaks per slice — you'll need
  `analyze_iq_spectrogram` variants that surface top-N peaks
  (not shipped today — flag for the operator).
- **Amplitude-modulated barcode.** Vertical bars encode a message
  in Baudot or ASCII; each bar's *duration* is the character.
- **Time-domain stego.** Text encoded in a Morse rhythm on top of a
  fake carrier. Detectable via `analyze_iq_modulation` reporting
  OOK with a very slow symbol rate (< 10 baud).

## Trap catalog

- **"The waterfall image is the flag."** Sometimes it *is* the flag
  verbatim; more often it's a clue pointing at a follow-up capture.
- **"Every band is meaningful."** Some CTFs pad with random-looking
  bands to hide the payload — read only the ones with a coherent
  vertical structure.
- **"You need a specialized tool."** No — matplotlib's `imshow` on
  the FFT matrix is enough.

## Failure modes

- **FFT size too small.** Blurs the letters. Retry with 4096-8192
  bins.
- **Wrong sample rate.** If the image is stretched vertically, the
  actual bandwidth is smaller than your capture; recapture with a
  narrower `sample_rate_hz`.
- **Not enough time samples.** Text spans seconds — a 100-ms capture
  will only show one column.

## Cross-references

- `../iq-analysis/reference.md` — spectrogram math
- `spectrogram-reading.md` — the general shape catalog
