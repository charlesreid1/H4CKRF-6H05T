# signal-generation-with-numpy/reference.md — the recipes

Every function below takes basic parameters (sample rate, symbol rate,
carrier offset) and returns a `complex64` array ready to be packed as
`.cs8`. All are runnable as-is with numpy + scipy.

## HackRF `.cs8` packing

Two lines from complex64 to bytes:

```python
def pack_cs8(iq_c64, path):
    i8 = np.clip((iq_c64.real * 127), -128, 127).astype(np.int8)
    q8 = np.clip((iq_c64.imag * 127), -128, 127).astype(np.int8)
    out = np.empty(2 * len(iq_c64), dtype=np.int8)
    out[::2], out[1::2] = i8, q8
    out.tofile(path)
```

## Sample-rate choice for HackRF

- Supported: 2, 4, 8, 10, 20 Msps.
- **Recommend 2-8 Msps** for TX; 20 Msps is USB-2-limited and drops
  samples on many hosts.
- Center all generation at DC — the HackRF's tuner shifts to the RF
  center on transmit.

## Amplitude scaling

The MAX5864 DAC is 8-bit. Aim for `max(|iq|) ~= 0.9` before packing —
leaves headroom without clipping. Push closer to 1.0 for stronger TX;
1.0 exactly will clip.

## Recipes

### AM (DSB-LC, tone-modulated)

```python
import numpy as np

def gen_am(fs, duration, audio_freq, mod_depth=0.5, fc_offset=0):
    n = int(fs * duration)
    t = np.arange(n) / fs
    audio = np.sin(2 * np.pi * audio_freq * t)
    envelope = 1 + mod_depth * audio
    carrier = np.exp(1j * 2 * np.pi * fc_offset * t)
    return (envelope * carrier).astype(np.complex64)
```

### FM (narrowband voice)

```python
def gen_fm(fs, duration, audio_freq, deviation=5000, fc_offset=0):
    n = int(fs * duration)
    t = np.arange(n) / fs
    audio = np.sin(2 * np.pi * audio_freq * t)
    phase = 2 * np.pi * deviation * np.cumsum(audio) / fs
    return np.exp(1j * (phase + 2 * np.pi * fc_offset * t)).astype(np.complex64)
```

### OOK

```python
def gen_ook(bits, fs, symbol_rate, fc_offset=0):
    sps = int(fs / symbol_rate)
    bits_at_fs = np.repeat(bits, sps).astype(np.float32)
    t = np.arange(len(bits_at_fs)) / fs
    carrier = np.exp(1j * 2 * np.pi * fc_offset * t)
    return (bits_at_fs * carrier).astype(np.complex64)
```

### 2FSK

```python
def gen_2fsk(bits, fs, symbol_rate, deviation=4500, fc_offset=0):
    sps = int(fs / symbol_rate)
    bits_at_fs = np.repeat(bits, sps).astype(np.float32)
    inst_f = np.where(bits_at_fs, +deviation, -deviation)
    phase = 2 * np.pi * np.cumsum(inst_f) / fs
    t = np.arange(len(phase)) / fs
    return np.exp(1j * (phase + 2 * np.pi * fc_offset * t)).astype(np.complex64)
```

### BPSK

```python
def gen_bpsk(bits, fs, symbol_rate, fc_offset=0):
    sps = int(fs / symbol_rate)
    bits_at_fs = np.repeat(bits.astype(np.int8) * 2 - 1, sps)  # {-1, +1}
    t = np.arange(len(bits_at_fs)) / fs
    return (bits_at_fs * np.exp(1j * 2 * np.pi * fc_offset * t)).astype(np.complex64)
```

### QPSK

```python
def gen_qpsk(bits, fs, symbol_rate, fc_offset=0):
    # bits length must be even
    b = bits.reshape(-1, 2)
    symbols = (2*b[:, 0] - 1) + 1j * (2*b[:, 1] - 1)
    symbols /= np.sqrt(2)
    sps = int(fs / symbol_rate)
    up = np.repeat(symbols, sps)
    t = np.arange(len(up)) / fs
    return (up * np.exp(1j * 2 * np.pi * fc_offset * t)).astype(np.complex64)
```

### Manchester-encoded OOK (315/433 MHz keyfob replay research)

```python
def gen_manchester_ook(bits, fs, symbol_rate, fc_offset=0):
    manchester = np.array([[1, 0] if b else [0, 1] for b in bits]).ravel()
    return gen_ook(manchester, fs, 2 * symbol_rate, fc_offset)
```

### LoRa CSS (simplified — one up-chirp symbol)

```python
def gen_lora_chirp(sf, bw, fs, sym_idx=0):
    N = 2 ** sf
    k = np.arange(N)
    # cyclic-shift start point to encode the symbol
    ref = np.exp(1j * np.pi * ((k + sym_idx) % N)**2 / N - 1j * np.pi * (k + sym_idx))
    # upsample to fs
    upsample = int(fs / bw)
    return np.repeat(ref, upsample).astype(np.complex64)
```

## Ethics + legality

Generating an IQ file is 100% legal. **Transmitting** it is subject to
the grant, the safety gate, and per-band regulatory rules. The corpus
must not conflate the two.
