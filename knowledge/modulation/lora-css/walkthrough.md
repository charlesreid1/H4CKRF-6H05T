# lora-css/walkthrough.md — dechirp + symbol recovery

Toy example — full LoRa decode is out of scope for numpy. This
walkthrough demonstrates dechirping and symbol recovery only.

## Preparation

```python
import numpy as np

fs = 2_000_000       # capture sample rate
sf = 7               # spreading factor
bw = 125_000         # 125 kHz channel bandwidth
sps_symbol = int(fs * (2**sf) / bw)   # samples per symbol
N = 2**sf            # FFT length after decimation

# assume iq is a captured LoRa preamble+data at 868.1 MHz, decimated
# to exactly BW samples/s (or an integer multiple)
iq_dec = iq[::int(fs / bw)]
sps_symbol_dec = 2**sf   # after decimation, one symbol = N samples
```

## Reference chirps

```python
k = np.arange(N)
ref_up = np.exp(1j * np.pi * (k**2) / N - 1j * np.pi * k)
ref_down = np.conj(ref_up)
```

## Symbol recovery

```python
def recover_symbol(sym_iq, ref_down):
    dechirped = sym_iq * ref_down
    spec = np.fft.fft(dechirped)
    return int(np.argmax(np.abs(spec)))

# split into symbol windows and recover each
symbols = []
for start in range(0, len(iq_dec) - N, N):
    idx = recover_symbol(iq_dec[start:start + N], ref_down)
    symbols.append(idx)

print(symbols[:16])
```

## Preamble detection

The preamble is 8 up-chirps → dechirping produces 8 consecutive `sym_idx=0`
values. If you see that in the first ~10 symbol windows, you've found
the preamble.

## What's next

Everything past preamble-and-sync-word:

1. Read the PHDR (header) — implicit or explicit mode changes semantics.
2. **Whitening reversal:** XOR payload with a Semtech-defined LFSR
   sequence.
3. **Gray de-mapping** on the symbol indices.
4. **Diagonal interleaver reversal** — SF-column × CR-row block.
5. **Hamming decoder** at the payload's coding rate.
6. **CRC-16 check.**

Beyond a paper exercise, use `gr-lora_sdr` — the EPFL fork has all the
above in tested C++ blocks.

## Waterfall analysis

If you just want to *identify* LoRa on the air (not decode it), no
math is needed — the diagonal streaks are unmistakable. See
`recognition.md`.
