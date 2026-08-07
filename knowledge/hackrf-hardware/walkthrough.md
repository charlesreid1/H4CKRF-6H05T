# hackrf-hardware/walkthrough.md — device operation recipes

## 1. Read the device state

```bash
hackrf_info
```

Expected output includes:

- **libhackrf version** — the host library
- **firmware version** — must be reasonably recent (2023+ is safe)
- **Serial number** — unique per device
- **Board ID** — should be `2 (HackRF One)`
- **Part ID Number** — MCU-specific, informational

If `hackrf_info` shows `USB error -1000: HACKRF_ERROR_NOT_FOUND`, the
kernel/OS did not enumerate the device — try a different USB port, a
data-capable cable, or check udev rules on Linux.

## 2. Update firmware

```bash
# Locate the firmware binary (macOS example)
FW=$(brew --prefix)/share/hackrf/firmware-bin/hackrf_one_usb.bin
# Write it
hackrf_spiflash -w "$FW"
# Unplug, wait a beat, replug
hackrf_info    # confirm the version bumped
```

The firmware image ships with the hackrf-tools package. On Ubuntu it
lives under `/usr/share/hackrf/firmware-bin/` (path varies by
package version — check `dpkg -L hackrf-tools | grep firmware`).

## 3. Discipline the clock with a GPSDO

Requires an external 10 MHz reference (a GPSDO puck like a Leo Bodnar
Mini-Precision GPS). Plug it into the CLK IN port on the HackRF.
Firmware auto-detects the external clock; `hackrf_info` will still
show the internal TCXO version but tuning will now be locked to the
external reference. Confirm by capturing a known-stable tone (e.g.
WWV/WWVH or a lab reference) and checking that its frequency drift
over 10 minutes is <0.01 Hz.

## 4. Understand your capture is 8 bits

A raw `hackrf_transfer` file is int8-interleaved (`.cs8`). To load:

```python
import numpy as np
raw = np.fromfile('capture.iq', dtype=np.int8)
x = raw[::2].astype(np.float32) / 127 + 1j * raw[1::2].astype(np.float32) / 127
```

Consequences of 8 bits:

- Signal amplitude values live in `[-1, +1]` after scaling.
- Anything above `1.0` in `|x|` is clipped by the ADC.
- Below about `1/128 ≈ 0.008` you're at the quantization floor —
  smaller signals need decimation to escape.

## 5. TX safety envelope

- **Never TX without a grant.** `hackrf-agent grant tx <band> --for
  <duration>` first.
- **Never TX above +14 dBm nominal.** The HackRF's output stage is
  small; higher gain risks distortion and possibly hardware damage
  into a mismatched load.
- **Use a dummy load** for bench testing, not an antenna. A 50 Ω
  dummy load turns TX into heat; an antenna turns it into a radio
  transmission.
- **Read `docs/safety.md`.** Especially the parts about ADS-B, GPS,
  and aviation voice.
