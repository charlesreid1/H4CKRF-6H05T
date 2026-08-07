# whitening-audit — a bit-scrambler is applied and must be reversed

Payloads look high-entropy but a whitening LFSR is applied on top of
a plaintext flag. Reverse the LFSR and the flag appears.

## What is whitening?

An LFSR generates a pseudo-random bit sequence with a known seed and
polynomial. The transmitter XORs the plaintext payload with the LFSR
output before transmission. The receiver XORs the received bits with
the *same* LFSR sequence to recover plaintext.

**Purpose (legit):** DC balance + break long runs so the receiver's
clock recovery stays locked. Used in Bluetooth, LoRa, Zigbee, IEEE
802.11.

**Purpose (CTF):** obscure the payload while still shipping a
plaintext-XOR-mask.

## Signature

- **Decoded payload is high-entropy** — no readable text, no obvious
  structure.
- **Same PHY for every packet** — the whitening LFSR is deterministic;
  identical positions in different packets XOR to identical bits.
- **XOR of two packets is short-lived-entropy** — since both are
  `plaintext_i XOR keystream_at_position_p`, XOR-ing them cancels the
  keystream and leaves `plaintext_a XOR plaintext_b`. This can be
  read as English if you know one plaintext.

## Decode workflow

1. Capture multiple packets, decode each to its payload.
2. If you have known-plaintext for one packet (e.g. the header), XOR
   the known plaintext against the ciphertext to recover a *fragment*
   of the whitening keystream. That fragment then decodes the same
   positions in other packets.
3. If you know the LFSR polynomial and init (e.g. LoRa uses a
   Semtech-specified LFSR), just generate the sequence and XOR.
4. If you know neither, use the **crib-drag** technique — assume the
   first N bytes are a probable prefix (e.g. `flag{`) and try to
   verify.

## LFSR sequence common in the wild

- **LoRa:** Semtech-defined LFSR with init `0xFF`, poly `x^8 + x^6 +
  x^5 + x^4 + 1`.
- **Bluetooth:** channel-dependent LFSR (see BT Core Spec).
- **802.11:** per-scrambler LFSR (see IEEE 802.11-2020 §17.3.5.5).
- **CTF-custom:** author chooses; often a 7-bit or 8-bit LFSR with a
  memorable poly like `0xE5`.

## Numpy sketch

```python
def lfsr(poly, init, length):
    """Generate `length` bits of an LFSR sequence."""
    state = init
    bits = []
    for _ in range(length):
        bits.append(state & 1)
        new_bit = 0
        for shift in range(poly.bit_length()):
            if (poly >> shift) & 1:
                new_bit ^= (state >> shift) & 1
        state = (state >> 1) | (new_bit << (poly.bit_length() - 1))
    return bits

# XOR ciphertext with the keystream
keystream = lfsr(poly=0xE5, init=0xFF, length=len(ciphertext_bits))
plaintext = [c ^ k for c, k in zip(ciphertext_bits, keystream)]
```

## Sanity checks

- If XOR-ing two same-length packets yields something with ASCII-like
  entropy → whitening confirmed. If it stays random → different mechanism
  (encryption, not just whitening).
- If the resulting plaintext has correct English trigrams or a
  recognizable flag prefix → the LFSR parameters were right.

## Cross-references

- `../crc-fec/reference.md`
- `../modulation/lora-css/reference.md` — LoRa whitening spec
- `packet-flag.md` — general "flag in packet"
