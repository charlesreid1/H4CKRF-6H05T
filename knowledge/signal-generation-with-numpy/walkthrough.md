# signal-generation-with-numpy/walkthrough.md — 433 MHz keyfob fixture

Complete recipe: generate a Manchester-encoded OOK 433 MHz keyfob-style
capture as a `.cs8` file the HackRF can transmit (with a grant).

## Assumptions

- **Target frequency:** 433.920 MHz (EU ISM, US Part 15 secondary).
- **Symbol rate:** 2 kbps (typical of older keyfobs).
- **Sample rate:** 2 Msps (comfortable, plenty of headroom).
- **Payload:** `0x1B 0x2E 0xA7 0x00` (address + counter + status).
- **Preamble:** 8 bits of `0xAA` (`10101010`).
- **Burst repeats:** 4× with 20 ms gap between.

## Code

```python
import numpy as np

def gen_manchester_bits(payload_bytes):
    """Convert a byte sequence to a Manchester-encoded bit stream."""
    bits = np.unpackbits(payload_bytes)
    manchester = np.array([[1, 0] if b else [0, 1] for b in bits]).ravel()
    return manchester

def gen_ook_manchester_burst(payload_bytes, fs, symbol_rate, preamble=0xAA, preamble_bits=8):
    """One burst = preamble + payload, Manchester-encoded on top of OOK."""
    pre_bytes = np.array([preamble] * (preamble_bits // 8), dtype=np.uint8)
    pre_manchester = gen_manchester_bits(pre_bytes)
    pay_manchester = gen_manchester_bits(payload_bytes)
    all_manchester = np.concatenate([pre_manchester, pay_manchester])

    sps_manchester = int(fs / (2 * symbol_rate))
    envelope = np.repeat(all_manchester, sps_manchester).astype(np.float32)
    return envelope  # baseband real envelope; complex-conj-conjugate trivial

def gen_burst_sequence(payload_bytes, fs, symbol_rate, burst_count=4, gap_ms=20):
    """burst_count bursts with gap_ms milliseconds of silence between."""
    one_burst = gen_ook_manchester_burst(payload_bytes, fs, symbol_rate)
    gap_samples = int(fs * gap_ms / 1000)
    gap = np.zeros(gap_samples, dtype=np.float32)
    seq_parts = []
    for _ in range(burst_count):
        seq_parts.extend([one_burst, gap])
    return np.concatenate(seq_parts)

def to_complex_baseband(envelope, fs, fc_offset=0):
    """Real envelope -> complex baseband. fc_offset=0 keeps it at DC."""
    t = np.arange(len(envelope)) / fs
    carrier = np.exp(1j * 2 * np.pi * fc_offset * t)
    return (envelope * carrier).astype(np.complex64)

def pack_cs8(iq_c64, path):
    i8 = np.clip((iq_c64.real * 127), -128, 127).astype(np.int8)
    q8 = np.clip((iq_c64.imag * 127), -128, 127).astype(np.int8)
    out = np.empty(2 * len(iq_c64), dtype=np.int8)
    out[::2], out[1::2] = i8, q8
    out.tofile(path)

if __name__ == "__main__":
    payload = np.frombuffer(bytes([0x1B, 0x2E, 0xA7, 0x00]), dtype=np.uint8)
    fs = 2_000_000
    symbol_rate = 2_000
    seq = gen_burst_sequence(payload, fs, symbol_rate)
    # scale down amplitude to leave DAC headroom
    seq *= 0.85
    iq = to_complex_baseband(seq, fs, fc_offset=0)
    pack_cs8(iq, "keyfob_fixture.cs8")
    print(f"wrote keyfob_fixture.cs8, {len(iq) / fs:.3f} s")
```

## Transmit path

Once the `.cs8` exists, transmission is subject to:

- A **grant** covering the target frequency + gain (see
  `PermissionService.covers_transmission()` in the MCP source).
- **Sub-ISM-band regulation:** 433.92 MHz is EU ISM under ETSI EN 300
  220, US Part 15 §15.231 (secondary). Keep TX VGA gain low.
- The **safety gate** (`RiskAssessor`) — 433.92 is not BLOCKED, but
  the operator still must approve.

The operator issues:

```
transmit_iq --iq keyfob_fixture.cs8 --freq 433920000 --tx-vga 10 --sample-rate 2000000
```

The MCP:

1. Validates `iq_path` is under the session root.
2. Checks the grant covers `(freq, gain)`.
3. Sends the file to `hackrf_transfer -t`.

## What operators sometimes miss

- **Numpy-clean signals have no phase noise.** A real keyfob has a
  crystal oscillator with ppm-level drift; numpy-generated signals
  are cycle-perfect. Add a small artificial jitter for realism.
- **Numpy-clean signals have no timing jitter.** Same idea; realistic
  bursts include ~µs symbol-boundary noise.
- **Numpy-clean signals have no amplifier compression.** Real transmit
  chains introduce 2nd/3rd-order distortion; numpy signals are
  linear-clean.

Those "too clean" tells can betray a lab-generated signal in a
"is this the real device?" CTF puzzle.
