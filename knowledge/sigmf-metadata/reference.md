# sigmf-metadata/reference.md — the schema

## The paired-file convention

- `<basename>.sigmf-data` — raw IQ payload (any SigMF datatype).
- `<basename>.sigmf-meta` — JSON metadata.

Both files must have the same basename; SigMF tooling refuses to load
one without the other.

## Core fields

```jsonc
{
  "global": {
    "core:datatype": "ci8",           // or ci16_le, cf32_le, cu8, ...
    "core:sample_rate": 2000000,
    "core:version": "1.0.0",
    "core:hw": "HackRF One",
    "core:author": "operator@example",
    "core:description": "keyfob press captures for CTF triage",
    "core:sha512": "..."              // integrity hash of the .sigmf-data file
  },
  "captures": [
    {
      "core:sample_start": 0,
      "core:frequency": 433920000,
      "core:datetime": "2026-08-07T14:30:00Z"
    }
  ],
  "annotations": [
    {
      "core:sample_start": 400000,
      "core:sample_count": 30000,
      "core:freq_lower_edge": 433910000,
      "core:freq_upper_edge": 433930000,
      "core:description": "press 1 - fixed-code candidate"
    }
  ]
}
```

## Datatype string convention

- `ci8` — complex signed int8 (HackRF native).
- `cu8` — complex unsigned int8 (rtl-sdr native).
- `ci16_le` — complex signed int16 little-endian (LimeSDR/USRP).
- `cf32_le` — complex float32 little-endian (GNU Radio default).
- `cf64_le` — complex float64 (scientific dumps).

`_le` suffix denotes byte order; `_be` for big-endian.

## Multi-capture segments

A single `.sigmf-data` file can contain multiple captures with
different center frequencies or sample rates via multiple entries in
the `captures` array — each entry marks the sample offset where its
parameters begin. Useful for concatenating a survey.

## Annotations

Time-and-frequency bounded metadata attached to a specific range of
samples. Free-form `core:description` plus optional
`core:freq_lower_edge`/`upper_edge`. Many tools (URH, SDRAngel) render
these on the spectrogram.

## Extensions

The SigMF working group maintains extensions for GPS, antenna, capture
segments, and more. First-pass corpus: base spec only. Extensions come
in as needed.

## Emit + ingest from numpy

```python
import json, hashlib, numpy as np

def emit_sigmf(iq_int8, basename, fs, fc):
    (iq_int8.astype(np.int8)).tofile(f"{basename}.sigmf-data")
    with open(f"{basename}.sigmf-data", "rb") as f:
        digest = hashlib.sha512(f.read()).hexdigest()
    meta = {
        "global": {
            "core:datatype": "ci8",
            "core:sample_rate": fs,
            "core:version": "1.0.0",
            "core:hw": "HackRF One",
            "core:sha512": digest,
        },
        "captures": [{"core:sample_start": 0, "core:frequency": fc}],
        "annotations": [],
    }
    with open(f"{basename}.sigmf-meta", "w") as f:
        json.dump(meta, f, indent=2)
```

## Citations

- SigMF spec v1.0 (sigmf-spec.md on GitHub).
- SigMF working group at github.com/sigmf/SigMF.
