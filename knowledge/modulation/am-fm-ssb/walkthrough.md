# am-fm-ssb/walkthrough.md — analog demod snippets

Every snippet below assumes `x` is complex baseband IQ at rate `fs`.

## Broadcast AM → audio WAV

```python
import numpy as np
from scipy.signal import decimate, butter, lfilter

env = np.abs(x)
env -= env.mean()                # drop DC
audio = decimate(env, int(fs / 44_100), ftype='fir')

# optional 5 kHz LPF for broadcast MW
b, a = butter(4, 5_000 / (44_100 / 2))
audio = lfilter(b, a, audio)
```

## Narrow-FM voice (airband, marine VHF, amateur repeaters)

```python
phase = np.unwrap(np.angle(x))
audio = np.diff(phase) * fs / (2 * np.pi)     # instantaneous frequency
audio -= audio.mean()

# resample to 24 kHz for voice
audio = decimate(audio, int(fs / 24_000), ftype='fir')

# 3 kHz voice LPF
b, a = butter(4, 3_000 / (24_000 / 2))
audio = lfilter(b, a, audio)
```

## Broadcast FM (mono)

```python
phase = np.unwrap(np.angle(x))
audio = np.diff(phase) * fs / (2 * np.pi)
audio = decimate(audio, int(fs / 240_000), ftype='fir')  # 240 kHz IF

# 75 μs de-emphasis (US)
tau = 75e-6
alpha = np.exp(-1 / (240_000 * tau))
b = [1 - alpha]
a = [1, -alpha]
audio = lfilter(b, a, audio)

audio = decimate(audio, int(240_000 / 48_000), ftype='fir')  # 48 kHz
```

The stereo pilot at 19 kHz and the DSB stereo at ±19 kHz around 38 kHz
require additional demodulation — omitted here.

## SSB (USB) — frequency-shift + LPF

```python
# assume x is baseband-centered on the suppressed carrier;
# USB means audio lives 0..3 kHz above it in complex baseband.
from scipy.signal import decimate

audio_lpf = 3_000
target_fs = 12_000

# discard the mirrored side by keeping only the real part after decimating
narrowband = decimate(x, int(fs / target_fs), ftype='fir')
audio = narrowband.real  # USB by convention; for LSB use .imag or complex-conj first
```

For a well-tuned receiver you also correct for small carrier offset
before the decimate. In the field, most SSB receivers give the operator
a "fine tune" knob for exactly this reason.
