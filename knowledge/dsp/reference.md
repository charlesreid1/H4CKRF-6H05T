# dsp/reference.md — the DSP primer

Everything downstream in this corpus references material that lives here.
First-pass depth: enough to answer "why does this spectrogram have a line
in the middle?" and "how do I estimate a symbol rate?" Full Oppenheim &
Schafer is out of scope.

## Sampling

**Nyquist–Shannon.** A signal band-limited to `B` Hz can be sampled at
`fs ≥ 2·B` without loss. For **complex baseband** (IQ) sampling, `fs`
covers `±fs/2` around DC — so an IQ stream at `fs = 10 Msps` observes
`-5 MHz … +5 MHz` around the tuned frequency.

**Aliasing / folding.** Content outside `[-fs/2, +fs/2]` folds back
in. A tone at `fs/2 + Δ` shows up at `fs/2 - Δ`. Real hardware has an
anti-alias filter; ignoring it, or under-sampling deliberately, is a
recipe for phantom signals.

**Decimation.** Downsampling by integer `M` (`x[::M]`) requires a
low-pass filter with cutoff `fs/(2M)` beforehand, or aliasing wins.
`scipy.signal.decimate(x, M, ftype='fir')` bundles the LPF and the
subsample. For non-integer rates, `scipy.signal.resample_poly(x, up,
down)`.

## IQ representation

**Complex baseband.** The HackRF (and every quadrature SDR) mixes the
RF signal against `cos(2π·f_tune·t)` (I) and `-sin(2π·f_tune·t)` (Q),
producing a complex sequence `x[n] = I[n] + j·Q[n]`. Positive
frequencies in `x` correspond to signals above `f_tune`; negative
frequencies to signals below. This is why negative frequencies "exist"
in an IQ file — they're one-sided real-world content shifted about the
tune.

The magnitude `|x[n]| = sqrt(I² + Q²)` is envelope; the argument
`angle(x[n]) = atan2(Q, I)` is instantaneous phase. Instantaneous
frequency is the derivative of phase: `np.diff(np.unwrap(np.angle(x)))
/ (2*pi/fs)`.

## Spectra

**FFT sizing.** An `N`-point FFT on `fs`-rate IQ produces `N` bins,
each `fs/N` Hz wide. Doubling `N` halves bin width but doubles the
capture window. You cannot resolve two tones separated by less than
`fs/N` Hz without a longer window.

**Zero-padding.** `np.fft.fft(x, n=4*len(x))` gives visual smoothness
but **not** true resolution. Real resolution is set by observation
time.

**Windowing.** Applying `x * window` before FFT tames spectral leakage
at the cost of main-lobe widening. Common windows:

- **Hann** (`np.hanning(N)`) — good general-purpose. ~1.5-bin main
  lobe, ~-32 dB sidelobes.
- **Hamming** — slightly lower first sidelobe, higher far sidelobes.
- **Blackman-Harris** — very low sidelobes (~-92 dB) at ~2-bin main
  lobe cost. Best for weak-signal detection near strong signals.

**Welch's PSD.** For an estimate of the power spectral density,
average the FFT of overlapped windows: `scipy.signal.welch(x, fs,
nperseg=1024)`. This trades resolution for smoothness.

**Spectrogram.** Slide the window across time and stack the FFTs. Bin
width `fs/N` on the frequency axis; step size `N-overlap` samples on
the time axis. `scipy.signal.spectrogram` does the bookkeeping.

## Filters

**FIR vs IIR.** FIR (finite impulse response) filters are linear-phase
and unconditionally stable. IIR are cheaper for the same skirt but can
ring or oscillate. Default to FIR for RF baseband processing unless
CPU budget forces otherwise.

**Design.** `scipy.signal.firwin(numtaps, cutoff, fs=fs)` for
low-pass, `firwin(..., pass_zero=False)` for high-pass, `bandpass` via
`[low, high]` cutoff. Rule of thumb: `numtaps ≈ 4 / transition_width`
in normalized units; more taps = sharper skirt.

**Application.** `scipy.signal.lfilter(b, 1, x)` for causal;
`filtfilt(b, 1, x)` for zero-phase (offline only, doubles the delay).

## Matched filtering

For a known pulse shape `h[n]` (root-raised-cosine, rectangular, Manch-
ester half-symbol), the matched filter is `h[-n]*`. Convolving the
received IQ with the time-reversed conjugate maximizes SNR at the
symbol instant. `np.convolve(x, np.conj(h[::-1]))`.

## Cyclostationarity — for symbol timing recovery

A digitally modulated signal has statistics that repeat at the symbol
rate. Two ways to find that rate blindly:

- **Autocorrelation of |x|².** Compute `r[k] = sum(|x[n]|² · |x[n+k]|²)`
  for a range of `k`. The first peak past `k=0` is at the symbol
  period `Ts = fs / symbol_rate`.
- **Spectral correlation density.** Multiply `X(f) · X*(f + α)` — a
  peak at cyclic frequency `α` = symbol rate indicates a repeating
  cycle.

Gardner and Mueller-Müller are the classic closed-loop symbol
timing-recovery methods; they refine an initial estimate rather than
find it from scratch.

## Hilbert transform

`scipy.signal.hilbert(real_signal)` returns the analytic signal
(complex, positive-frequency-only). Useful when handed a real-valued
recording (e.g. a WAV file) that needs to be reinterpreted as complex
baseband. `abs(hilbert(x))` is the envelope.
