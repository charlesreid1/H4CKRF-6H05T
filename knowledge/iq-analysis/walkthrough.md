# iq-analysis — walkthrough

Three worked examples of using the analysis verbs to answer a real
question about an IQ capture.

## 1. "Is anything on this frequency?"

Given a capture at 433.92 MHz for 500 ms:

```jsonc
capture_iq({"target_freq_hz": 433_920_000, "sample_rate_hz": 2_000_000, "duration_s": 0.5})
// -> {"iq_path": ".../capture-01.iq", ...}

read_iq_summary({"iq_path": ".../capture-01.iq", "center_freq_hz": 433_920_000 + 500_000})
// -> {"noise_floor_dbfs": -72.0, "peak_dbfs": -28.0, "peak_freq_hz": 433_920_000, "occupancy_pct": 1.8}
```

Read: SNR ≈ 44 dB, occupancy near 2% — one narrow signal, plenty of margin
above noise. Something is there.

## 2. "What modulation is it?"

Continue with `analyze_iq_modulation`:

```jsonc
analyze_iq_modulation({"iq_path": ".../capture-01.iq", "sample_rate_hz": 2_000_000})
// -> {"candidates": [
//      {"family": "OOK", "confidence": 0.82, "note": "high peak-to-mean; envelope variance dominant"},
//      {"family": "2FSK", "confidence": 0.14, "note": "phase-continuous but envelope also modulated"},
//      {"family": "PSK", "confidence": 0.04, "note": ""}
//    ]}
```

OOK wins. High peak-to-mean ratio is the classic OOK signature — the
signal is on-or-off. Compare with `knowledge_lookup_modulation("OOK")`
to confirm this looks like the reference OOK envelope.

## 3. "What's the symbol rate, and can I decode it?"

Feed the same IQ into `analyze_iq_symbols`:

```jsonc
analyze_iq_symbols({"iq_path": ".../capture-01.iq", "sample_rate_hz": 2_000_000})
// -> {"symbol_rate_hz": 2050.0, "confidence": 0.73, "lag_samples": 976}
```

Symbol rate ~2 kbps at 433.92 MHz OOK — that's textbook keyfob /
weather-station territory. The 2 kbps clock rules out POCSAG (512/1200
baud FSK) and BLE (1 Msym GFSK). Try Manchester at 2050 baud:

```jsonc
decode_manchester({
  "iq_path": ".../capture-01.iq",
  "sample_rate_hz": 2_000_000,
  "symbol_rate_hz": 2050.0,
  "polarity": "ieee"
})
// -> {"bits": "1010...", "invalid_pairs": 3, "num_symbols": 128}
```

If `invalid_pairs > num_symbols/4`, flip polarity ("thomas") and retry —
some keyfob vendors invert Manchester. If polarity flip doesn't help,
the bit-level line code may be PWM instead; run
`knowledge_lookup_decoder("PWM")` to confirm the parameter names and try
`decode_pwm` next.

## 4. When the modulation classifier hedges

If `analyze_iq_modulation` returns two candidates within 0.2 confidence
of each other, don't guess — try the top candidate's decoder, and if it
fails (`invalid_pairs > threshold`), try the second. The classifier is a
starting point, not a verdict.

## 5. When the symbol-rate estimate is noisy

Low `confidence` (< 0.4) usually means one of:

- Not enough symbols in the capture — try a longer `duration_s`.
- Very low SNR — increase gain or move the antenna.
- The signal is chirp-spread (LoRa CSS) — symbol-rate estimator does not
  apply; use `knowledge_lookup_protocol("LoRa")` for the alternate path.

## Cross-references

- `knowledge/modulation/recognition.md` for how each family looks in a
  spectrogram
- `knowledge/decoders/` for what each `decode_*` verb expects
- `knowledge/crc-fec/` for how to verify a decoded frame
