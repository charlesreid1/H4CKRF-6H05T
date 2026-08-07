# dsp/walkthrough.md — runnable numpy snippets

Each snippet is short and standalone. `x` is a complex IQ array,
`fs` is the sample rate in Hz.

## 1. Estimate the spectrum

```python
import numpy as np
from scipy.signal import welch

f, Pxx = welch(x, fs=fs, nperseg=4096, return_onesided=False)
f = np.fft.fftshift(f)
Pxx = np.fft.fftshift(Pxx)
# f is in Hz, symmetric around 0; Pxx is linear power/Hz.
```

`np.fft.fftshift` moves DC to the center so a plot reads "negative
frequencies on the left, positive on the right."

## 2. Spectrogram (waterfall)

```python
from scipy.signal import spectrogram

f, t, Sxx = spectrogram(x, fs=fs, nperseg=1024, noverlap=512,
                        return_onesided=False)
f = np.fft.fftshift(f)
Sxx = np.fft.fftshift(Sxx, axes=0)
# t is seconds; f is Hz; Sxx is |X(f,t)|² in linear power.
db = 10 * np.log10(Sxx + 1e-12)
```

## 3. Remove the DC spike

```python
# Simple approach — subtract the mean.
x_ac = x - np.mean(x)

# Better — a shallow high-pass at ~1 kHz.
from scipy.signal import firwin, lfilter
taps = firwin(129, cutoff=1_000, fs=fs, pass_zero=False)
x_hp = lfilter(taps, 1.0, x)
```

If the capture is centered on the signal you want, prefer `target_freq_hz`
at capture time (see `../sdr-fundamentals/reference.md`) — a filter after
the fact can't undo an ADC dynamic-range steal.

## 4. Decimate to a lower sample rate

```python
from scipy.signal import decimate

# fs=10e6 → fs=1e6 (factor 10, do it in two 5x stages for numerical safety).
x_1msps = decimate(decimate(x, 5, ftype='fir'), 2, ftype='fir')
```

Cascade decimations when the factor is > 12 or so; the anti-alias filter
gets easier to design.

## 5. Instantaneous envelope (AM/OOK demod)

```python
env = np.abs(x)
# For OOK, threshold at (min + max)/2 to get bits at fs; then match to
# your symbol rate.
```

## 6. Instantaneous frequency (FM/FSK demod)

```python
phase = np.unwrap(np.angle(x))
inst_freq_hz = np.diff(phase) * fs / (2 * np.pi)
```

`inst_freq_hz` has length `len(x) - 1`. For 2FSK, threshold at the
midpoint between the two frequency lobes.

## 7. Symbol-rate estimation via autocorrelation

```python
env2 = np.abs(x)**2
env2 -= env2.mean()
# Focus on lags corresponding to plausible symbol rates.
min_rate, max_rate = 100, 100_000  # Hz
lag_max = int(fs / min_rate)
lag_min = int(fs / max_rate)
corr = np.array([np.dot(env2[:-k], env2[k:]) for k in range(lag_min, lag_max)])
peak_lag = lag_min + np.argmax(corr)
symbol_rate_hz = fs / peak_lag
```

For a clean OOK/Manchester signal this nails the rate; for noisier
captures, longer observation + averaging over multiple bursts helps.

## 8. Matched filter for a known pulse

```python
h = np.ones(int(fs / symbol_rate_hz), dtype=np.complex64)  # rectangular
y = np.convolve(x, np.conj(h[::-1]), mode='same')
# y is the matched-filtered signal; sample it at symbol instants.
```

## 9. Real WAV → analytic IQ

```python
from scipy.signal import hilbert
from scipy.io import wavfile

fs_wav, x_real = wavfile.read('capture.wav')
x_iq = hilbert(x_real.astype(np.float32))
# One-sided; positive frequencies of x_real are preserved.
```
