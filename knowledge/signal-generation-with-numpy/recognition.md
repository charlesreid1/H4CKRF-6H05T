# signal-generation-with-numpy/recognition.md — the "is this the real device?" tell

Numpy-generated signals have distinctive artifacts on the air. Ways to
spot them in a WCTF-style challenge:

## Cleaner sidelobes than the real thing

A real transmitter has:

- **Phase noise** — the LO isn't perfectly stable; adjacent-channel
  power is nonzero.
- **Amplifier nonlinearity** — 2nd and 3rd-order intermodulation
  products.
- **Timing jitter** — the crystal drives symbol boundaries with ± few
  ppm error.

A numpy-generated signal has none of the above. Symbol boundaries land
exactly on the sample grid; the constellation is razor-sharp; sidelobes
are pure sinc functions.

## Constant envelope where it shouldn't be

If the modulation is *supposed* to have envelope variation (like PWM
over OOK, or a non-ideal amplifier chain producing 5% AM), and yet
`np.abs(x)` is completely flat, that's numpy.

## Cycle-perfect symbol rates

A real 2 kbps signal has slight symbol-rate drift. A numpy signal
generated at `symbol_rate=2000` and `fs=2_000_000` gives *exactly*
1000 samples per symbol. If autocorrelation shows a peak at exactly
`fs / symbol_rate` samples with zero variance, that's a tell.

## No transient at start

Real transmitters ramp up over some fraction of a millisecond. A
numpy signal starts at maximum amplitude on sample zero. Absence of a
soft attack is a tell.

## Mitigations (if generating for research)

- Add gaussian phase noise: `x *= np.exp(1j * 0.01 * np.random.randn(len(x)))`.
- Jitter symbol boundaries: shift each symbol by `± int(0.005 * sps)`
  samples randomly.
- Simulate class-C compression: `x = np.tanh(np.abs(x)) *
  np.exp(1j * np.angle(x))`.
- Add a soft-start ramp: multiply first N samples by a rising envelope.
- Add finite-precision quantization: `x = np.round(x * 127) / 127`.

## What the MCP promises

- **`generate_iq` (or a numpy sketch handed to the operator)** is
  documented as "clean synthesis" — the corpus explicitly says operators
  should not expect it to fool a WCTF authenticity check.
- **`capture_iq`** is the truth-teller; a captured real-world signal
  carries all the pathologies above and can be confidently declared
  "the real thing" (subject to CTF puzzle-specific constraints).
