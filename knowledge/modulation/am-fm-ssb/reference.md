# am-fm-ssb/reference.md — analog modulation

## AM (Amplitude Modulation)

**DSB-LC (double sideband, large carrier):** `s(t) = (1 + m·a(t)) · cos(2π fc t)`
where `a(t)` is the audio and `m` (0..1) is modulation depth. Bandwidth
is `2 · audio_bw`. Broadcast MW and airband voice.

**DSB-SC (double sideband, suppressed carrier):** same but no carrier
term. Needs a coherent receiver (Costas loop or PLL) — envelope detection
fails.

**Audio bandwidths in practice:**

- Broadcast AM (US MW): 10 kHz per channel; audio ~5 kHz max.
- Airband AM (§Part 87): 8.33 or 25 kHz spacing; audio ~3 kHz.

## FM (Frequency Modulation)

`s(t) = cos(2π fc t + β · sin(2π fm t))` for a tone, or more generally
`cos(2π fc t + 2π kf · ∫ a(τ) dτ)`. Constant envelope — |s| doesn't
depend on the modulation.

**Carson's rule:** occupied bandwidth ≈ `2 · (Δf + f_audio_max)` where
`Δf` = peak deviation. Broadcast FM: Δf=75 kHz, audio 15 kHz → ~180 kHz.
Narrow FM voice: Δf=5 kHz, audio 3 kHz → ~16 kHz.

**De-emphasis:** broadcast FM pre-emphasizes high audio frequencies (75 μs
US / 50 μs EU) to improve SNR at TX; receiver applies matching de-emphasis
after demod. Missing it makes the output tinny.

## SSB (Single Sideband)

Suppress one sideband and the carrier. Bandwidth is `1 · audio_bw` —
half of AM. Two conventions:

- **USB (upper sideband):** keep the sideband above fc. Used above 10 MHz
  by amateur convention.
- **LSB (lower sideband):** keep the sideband below fc. Used below 10 MHz.

**Two generation methods** — phasing (Hilbert transform on audio, then
mix with I and Q of the carrier) and filter (generate DSB then remove one
sideband with a sharp filter).

## Citations

- Proakis & Salehi, *Digital Communications*, ch. 3 — analog modulation.
- FCC Part 15 (broadcast + generic), Part 87 (airband), Part 97 (amateur).
- Ossmann SDR lecture series.
