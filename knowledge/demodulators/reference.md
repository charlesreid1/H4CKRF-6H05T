# demodulators — reference

The numpy-scale sketch of every demod pipeline `hackrf_agent` uses. Each
demodulator takes IQ samples and outputs a real-valued signal that a
downstream decoder slices into bits.

## AM (amplitude modulation) → envelope

```
env = np.abs(iq)          # magnitude across time
env -= np.mean(env)       # remove DC
env /= np.max(np.abs(env)) + 1e-9  # normalize
```

The envelope is the audio (or the OOK-slicing input). Use a low-pass
filter at the audio bandwidth for clean voice recovery.

## FM (frequency modulation) → instantaneous frequency

```
phase = np.angle(iq)                       # instantaneous phase
inst_freq = np.diff(np.unwrap(phase))      # discrete-time derivative
inst_freq *= sample_rate_hz / (2 * np.pi)  # scale to Hz
```

The `diff` of unwrapped phase is the instantaneous frequency deviation
from the carrier. Feed it into an audio band-pass for narrowband FM
(voice, POCSAG, RTTY).

## OOK (on-off keying) → magnitude + slicing

```
env = np.abs(iq)
env_lp = low_pass(env, cutoff=symbol_rate_hz * 4)
threshold = (np.min(env_lp) + np.max(env_lp)) / 2
bits = env_lp > threshold  # boolean array at sample rate
```

Threshold at the midpoint of min/max — robust for constant-power OOK
bursts. Median works when the signal is bursty (mostly OFF).

## 2FSK → discriminator

```
inst_freq = np.diff(np.unwrap(np.angle(iq))) * (fs / (2 * np.pi))
# Mid-symbol threshold: min/max midpoint (better than median for
# idle-mark-heavy streams like RTTY)
threshold = (np.min(inst_freq) + np.max(inst_freq)) / 2
bits = inst_freq > threshold
```

The shared `fsk_bit_stream` primitive in `hackrf_agent.hw.analysis`
implements exactly this pipeline for POCSAG / RTTY / AX.25.

## GFSK → same as 2FSK but pre-filter

A Gaussian pulse-shaping filter at the transmitter narrows the spectrum
but blurs the transitions. In practice, treat GFSK captures the same as
2FSK and rely on the receive matched filter's tolerance. Only distinguish
GFSK from 2FSK if the classifier asks — the BT product (Bluetooth ≈ 0.5,
GSM ≈ 0.3) is not a bit-decision input.

## MSK / GMSK → I·Q correlation

MSK is a special case of continuous-phase FSK with `h = 0.5`. The
demodulator uses a matched filter or a coherent I/Q correlator:

```
# Coherent MSK demod (simplified)
i_after_lp = low_pass(iq.real, cutoff=symbol_rate/2)
q_after_lp = low_pass(iq.imag, cutoff=symbol_rate/2)
even_bits = np.sign(i_after_lp[::2])
odd_bits  = np.sign(q_after_lp[1::2])
bits = interleave(even_bits, odd_bits)
```

GMSK (GSM downlink) adds Gaussian pulse shaping — same recipe, matched
filter absorbs the shaping.

## BPSK / QPSK → decision regions

```
# Assumes carrier already stripped (baseband IQ)
symbols = iq[::samples_per_symbol]  # decimate to one sample per symbol
# BPSK: sign(real) is the bit
bpsk_bits = symbols.real > 0
# QPSK: (sign(I), sign(Q)) is a two-bit symbol
qpsk_bits = list(zip(symbols.real > 0, symbols.imag > 0))
```

Coherent recovery needs a Costas loop or a preamble; the H4CKRF stack
doesn't ship a PSK demod today. If the classifier suggests PSK, note
it and recommend the operator use GNU Radio for the recovery.

## OFDM → FFT per symbol

OFDM demod is out of scope for the H4CKRF agent; the classifier
identifies it (wide flat brick) but decoding requires cyclic-prefix
removal, channel estimation, and per-subcarrier equalization. Refer the
operator to a WiFi or LTE-specific tool.

## LoRa CSS → dechirp

```
# Dechirp: multiply by conjugate of the reference upchirp
dechirped = iq * np.conj(reference_chirp)
# FFT of dechirped signal — bin index is the symbol value
sym = np.argmax(np.abs(np.fft.fft(dechirped)))
```

Spreading factor and bandwidth determine samples-per-symbol. LoRa
decode is niche and not shipped today; the classifier flags it and the
operator escalates.

## Filter design — one paragraph

Most H4CKRF demod pipelines want a real-coefficient FIR low-pass at
around `symbol_rate * 2` (audio bandwidth after FM discriminator) or
`symbol_rate * 4` (OOK envelope). `scipy.signal.firwin(numtaps=127,
cutoff=cutoff, fs=fs)` is fine as a default. IIR filters are cheaper
per-sample but harder to reason about phase-wise — prefer FIR.

## Cross-references

- `knowledge/modulation/` for the per-family definitions
- `knowledge/decoders/` for the slicers that consume demod output
- `knowledge/iq-analysis/` for symbol-timing recovery before slicing
