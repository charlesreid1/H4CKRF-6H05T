# ask-ook/walkthrough.md — 433 MHz keyfob to hex bits

End-to-end pipeline in ~30 lines of numpy. Assumes a HackRF `.cs8`
capture at 433.92 MHz, `fs=2_000_000`, holding a couple of keyfob
presses.

```python
import numpy as np

# 1. Load HackRF .cs8 into complex64
raw = np.fromfile("capture.cs8", dtype=np.int8)
iq = (raw[::2] + 1j * raw[1::2]).astype(np.complex64) / 128.0
fs = 2_000_000

# 2. Envelope-detect (OOK is amplitude-modulated)
env = np.abs(iq)

# 3. Otsu-style threshold (mid-way between min and max)
threshold = (env.min() + env.max()) / 2
bits_at_fs = env > threshold

# 4. Estimate symbol rate via autocorrelation of the envelope
env_ac = np.correlate(env - env.mean(), env - env.mean(), mode='full')
env_ac = env_ac[env_ac.size // 2:]
peak_lag = np.argmax(env_ac[100:]) + 100   # skip 0-lag
symbol_rate = fs / peak_lag
sps = int(round(fs / symbol_rate))
print(f"symbol_rate ≈ {symbol_rate:.0f} bps, samples_per_symbol={sps}")

# 5. Decimate to one sample per half-bit (Manchester needs 2 samples/bit)
half = sps // 2
env_ds = env[::half].astype(bool)

# 6. Manchester decode: pair up half-symbols; transition-low-to-high = 0,
# transition-high-to-low = 1 (IEEE 802.3 convention; invert if wrong)
pairs = env_ds[:-1:2], env_ds[1::2]
bits = np.where(pairs[0] & ~pairs[1], 1, 0)
# (real code also needs to align to preamble first — see rtl_433 -A)

# 7. Pack to bytes for inspection
def bits_to_hex(bits):
    b = np.packbits(bits.astype(np.uint8))
    return ' '.join(f'{x:02X}' for x in b)

print(bits_to_hex(bits))
```

**What the operator does after this:**

- If bit patterns identical across presses → fixed-code keyfob; replay
  works (subject to law + consent).
- If the last N bits increment by 1 per press → rolling-code keyfob;
  fresh replay is defeated by the receiver.
- If bits look scrambled press-to-press → cryptographic rolling
  (Keeloq NLFSR, HITAG2, or newer AES). Not fresh-replay attackable.

**When numpy is not enough:**

Reach for `rtl_433 -A capture.cs8` — it runs the same envelope + auto
symbol-rate + attempt-every-decoder pipeline. If `rtl_433 -A` finds
nothing, `urh` gives you the GUI with cursor-based symbol timing.
