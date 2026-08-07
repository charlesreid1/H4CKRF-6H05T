# ism-868-915/recognition.md — LPWAN-shaped waterfalls

## The diagonal chirp streak

LoRa's chirp spread spectrum is the most visually distinctive signal
in the sub-GHz LPWAN band. Every symbol is one full up-chirp (or
down-chirp for the sync/downlink). On a waterfall you see diagonal
streaks going from low to high frequency across the channel bandwidth.

- **125 kHz BW, SF7:** chirp period ~1 ms. Streaks are visible on any
  reasonable spectrogram.
- **500 kHz BW, SF12:** chirp period ~66 ms. Very slow diagonals.
- **US915 has 8 sub-bands of 8 × 125 kHz uplink channels.** Bursts
  hop between them.

## The narrow constant tone

Sigfox's ~100 Hz uplink shows up as a hair-thin vertical line on a
waterfall. You need a very-narrow-band FFT (fft_size > 32768) to see
it at 2 MHz sample rate. Bursts last ~1 second.

## Z-Wave / wM-Bus

Narrow GFSK bursts at 40 kHz occupied bandwidth. Look like
2FSK-shaped short pulses (see `../modulation/recognition.md`).
Z-Wave EU is 868.42 MHz; US 908.42 MHz.

## Constant carrier at 869.525 MHz (EU)

LoRa RX2 downlink carrier, unmodulated when idle. Don't try to
transmit near it — 869.4–869.65 has strict duty cycle and gateway
rules.

## Capture pipeline

1. **Sweep broadly.** `sweep_spectrum` over the full band with 1 s
   dwell to catch bursty activity.
2. **Narrow the target.** Once you see a chirp signature, retune to
   its center with `target_freq_hz`.
3. **Recognize the modulation.** `analyze_iq_modulation` will flag
   OOK/2FSK/constant-envelope but won't classify CSS directly. Use
   `analyze_iq_spectrogram` and look at `peak_freqs_hz` — if it
   sweeps monotonically then wraps, it's a chirp.

## CTF flag patterns

- **The chirp direction IS the flag.** Up-chirps vs down-chirps
  distinguish LoRa uplink sync (up) from downlink (down).
- **The SF (spreading factor) IS the flag.** Higher SF = longer
  chirps = wider on-air time.
- **The frequency hop pattern IS the flag.** US915 uplinks hop across
  64 channels; the sequence can hide a message.
- **The Sigfox uplink narrowness IS the flag.** A 100 Hz signal that
  you can barely see is the target's clue that they used Sigfox.

## Common pitfalls

- **A 125 kHz LoRa capture at 250 kHz sample rate is not enough.**
  Sample at 2 MHz to give the chirp room to sweep without folding.
- **The HackRF's 8-bit ADC will clip on nearby WiFi.** 2.4 GHz WiFi
  can bleed into 900 MHz on a poor front end. Lower LNA gain.
- **LoRaWAN payloads are encrypted.** You see the PHY, not the app
  data. This is by design.
