# sdr-fundamentals/reference.md — the SDR-specific bits

What separates a HackRF from a spectrum analyzer or a signal generator.
This file focuses on the analog-to-digital boundary and the pathologies
that live there.

## Front-end topologies

- **Superheterodyne.** RF → mix to a high IF → filter → mix to a low
  IF → filter → sample. Excellent image rejection because the IF
  filter is fixed. Costly, big.
- **Direct conversion (zero-IF).** RF → mix to 0 Hz → sample as IQ.
  Cheap, small, and the topology the HackRF uses. Trades hardware
  cost for the pathologies described below.
- **Direct sampling.** ADC at RF, no mixer. Used above the ADC's
  fundamental Nyquist zone with aliased-band selection. RTL-SDR v3+
  in "direct sampling mode" hits HF this way.

## Zero-IF pathologies

**DC spike.** The LO leaks into the mixer's RF port, and any DC
offset in the baseband amps rides right through the ADC. Both show
up at exactly the tune frequency (0 Hz in complex baseband). Effects:
a tall narrow spike that is not a signal; ADC dynamic range partially
consumed by a fake tone. See `../dsp/recognition.md` for the visual.

**IQ imbalance.** If the I and Q chains have different amplitude gain
or their LO signals are not exactly 90° apart, every real-world tone
at frequency `+f` produces an "image" ghost at `-f`. Perfect balance
→ image at −∞ dB. HackRF factory-calibrated → typically 30–40 dB
image rejection. Consequences: a signal at `+100 kHz` looks like it
has a copy at `-100 kHz`. Corrections use a first-order affine model
on the IQ vector.

**LO leakage.** The tune-frequency LO radiates faintly out the RX
antenna port. Effect: your HackRF weakly transmits its own tune. In a
crowded lab this can interact with other SDRs. It is well below any
regulatory limit but explains "why do I see a spike on my other SDR
when this one tunes?"

## `target_freq_hz` vs `center_freq_hz`

This is the operational fix for the DC spike, and it lives in
`src/hackrf_agent/domain/handlers.py` behind the `capture_iq` action.

- `center_freq_hz` = raw tuner center. If your signal of interest is
  at this exact frequency, the DC spike lands on top of it.
- `target_freq_hz` = frequency of interest. The agent tunes the
  hardware to `target_freq_hz + fs/4` (roughly), so the DC spike sits
  at the edge of the passband and your signal sits comfortably
  inside.

**Prefer `target_freq_hz` unless you need raw tuner control** — see
`src/hackrf_agent/ai/prompts.py:110` for the LLM-facing version of
this rule.

## Gain staging

Order matters. In an ideal chain the LNA is right at the antenna, IF
gain sits in the middle, and baseband gain (VGA) is last. On the
HackRF:

- **RF amp (`amp`, 0 / +14 dB switch).** Enable only if the antenna
  input is quiet. Enabling with a strong nearby signal causes LNA
  compression.
- **LNA gain (`lna_gain_db`, 0–40 dB in 8 dB steps).** Sets front-end
  sensitivity. Start at 16 dB and adjust.
- **VGA gain (`vga_gain_db`, 0–62 dB in 2 dB steps).** Post-mixer
  baseband gain. Doesn't help SNR (mixer noise already added) but
  scales into the ADC's dynamic range.

**Rule of thumb.** Turn RF amp OFF for a survey sweep of an unknown
band. Add gain only after confirming you don't see clipping (flat-top
envelope) or LNA compression (harmonics/IM products).

## ADC dynamic range

The HackRF's ADC is 8-bit interleaved (MAX5864). Practical dynamic
range is ~48 dB SFDR. This means a strong nearby signal — an FM
broadcaster three miles away, an active WiFi router at 2.4 GHz —
consumes most of the dynamic range and leaves little for the weak
signal you care about. Fixes:

- Add an external bandpass filter at the antenna.
- Reduce LNA/VGA gain until the strong signal is well below clipping.
- Move the antenna. Physical isolation is free dB.

## Sample rate selection

- `2 Msps` is the minimum where the HackRF filters cooperate well.
- `10 Msps` is a common comfortable rate — plenty of bandwidth for
  keyfobs, weather stations, LPWAN.
- `20 Msps` is the theoretical maximum. USB 2.0 (480 Mbps) can just
  handle the 8I+8Q = 16 bits × 20 Msps = 320 Mbps stream, but any
  scheduling hiccup on the host will cause sample drops.

**Oversampling.** For a narrow signal, capturing at 5× to 10× the
signal bandwidth and then decimating gives ~2.5–5 dB of noise
shaping (spread quantization noise, keep it after the LPF).
