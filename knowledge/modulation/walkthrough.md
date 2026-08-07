# modulation/walkthrough.md — sketched demod pipelines

Short recipes. Each assumes `x` is complex baseband IQ at `fs` Hz.

## OOK

```python
env = np.abs(x)
threshold = (env.min() + env.max()) / 2
bits_at_fs = env > threshold
```

Downsample `bits_at_fs` to the symbol rate (see
`../dsp/walkthrough.md#7` for symbol-rate estimation) then apply
Manchester or NRZ decoding.

## 2FSK

```python
phase = np.unwrap(np.angle(x))
inst_freq = np.diff(phase) * fs / (2 * np.pi)
midpoint = np.median(inst_freq)
bits_at_fs = inst_freq > midpoint
```

The `midpoint` estimate is robust if 0s and 1s are roughly balanced;
if not, use the mean of the two histogram peaks.

## FM (narrowband voice)

```python
phase = np.unwrap(np.angle(x))
audio = np.diff(phase) * fs / (2 * np.pi)
audio = scipy.signal.decimate(audio, int(fs / 24_000))  # → 24 kHz audio
```

Add deemphasis (a single-pole LPF at ~2 kHz) if it's broadcast FM.

## AM (envelope)

```python
audio = np.abs(x)
audio -= audio.mean()
audio = scipy.signal.decimate(audio, int(fs / 24_000))
```

Envelope detection is the correct AM demod when there's a residual
carrier (broadcast AM, airband voice). For DSB-SC you'd need a Costas
loop.

## BPSK / QPSK — timing + constellation

```python
# 1. Coarse frequency correction (Costas or a squaring loop).
# 2. Matched-filter with an RRC (α=0.35 typical).
# 3. Symbol timing recovery (Gardner or Mueller-Müller).
# 4. Sample at symbol instants → constellation points.
# 5. Slice: BPSK → sign of real part; QPSK → sign of real & imag.
```

For CTF-level BPSK, a low-effort recipe:

```python
# assume x already close to symbol rate — decimate to 2 samples/symbol
# assume phase is roughly aligned
sym = x[::samples_per_symbol]
bits = (sym.real > 0).astype(int)
```

Real receivers are much fussier; this works only when the capture is
clean and near-baseband.

## LoRa (CSS)

Out of scope for a numpy sketch — LoRa's dechirp step is well-defined
but the framing (implicit vs explicit header, LDPC/Hamming FEC,
whitening) requires a full decoder. Use `gr-lora_sdr` or similar.
Recognize LoRa on the waterfall (see `recognition.md`) and hand the
file to a dedicated decoder.
