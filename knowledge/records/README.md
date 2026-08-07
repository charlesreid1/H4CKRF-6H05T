# knowledge/records/ — typed knowledge repo

JSON records shape the "numbers live here" half of the corpus. Each file in
this directory is a JSON array of records with a shared envelope; the
knowledge-retrieval MCP verbs (`knowledge_lookup_band`,
`knowledge_lookup_modulation`, `knowledge_lookup_protocol`, …) load these
files at runtime and return records verbatim.

## Envelope

Every record carries:

```jsonc
{
  "id": "kebab-case-slug-unique-within-file",
  "name": "Human name",
  "aliases": ["Alternate", "Names"],
  "category": "typed by file",
  "era_bounds": {"start": "1980", "end": null},   // null == still current
  "region": ["NA", "EU", "JP", "global"],
  "citations": ["cite-id-1", "cite-id-2"],        // → bibliography.json
  "confidence": "primary|secondary|community|folklore",
  "see_also": ["other-record-id"],
  "disputed": {"claim": "…", "position": "…"}      // optional
  // + per-record-type fields
}
```

## Files

Files below the envelope layer their own required fields. Full schemas are
authored in `../../plan-knowledge.md`; the short version:

- `bands.json` — allocated bands: `freq_min_hz`, `freq_max_hz`,
  `blocked_tx`, `primary_use`, `common_modulations`, per-region variants.
- `modulations.json` — modulation families: `bandwidth_hz_typical`,
  `symbol_rate_hz_range`, `spectral_signature`, `canonical_use`.
- `protocols.json` — RF protocols: `phy`, `framing`, `timing`,
  `decoder`, `fixture`.
- `keyfobs.json` — keyfob systems: `vendor`, `phy`, `crypto`,
  `replay_status`.
- `chipsets.json` — HackRF internals + adjacent SDRs (RTL-SDR, Airspy,
  LimeSDR, USRP B200).
- `iq-formats.json` — `.iq`, `.cf32`, `.cs8`, `.cs16`, SigMF byte layout.
- `decoders.json` — Manchester, PWM, PPM, NRZ, NRZI parameter ranges.
- `known-signals.json` — canonical signals seen at known frequencies.
- `regulatory.json` — regulatory categories. **Documentation only.**
  `RiskAssessor` does not read this file. The BLOCKED table stays
  hardcoded in Python.
- `bibliography.json` — sources with pinpoint cites.

## Loader contract

- Files are read fresh on every MCP process start; no per-session
  persistence.
- Path traversal is denied at the handler boundary. Records reference
  each other by `id`; free-text search is a separate verb.
- Missing `citations` is a hard validation error. Missing `disputed` is
  fine.
- `confidence: folklore` records are returned but flagged; the LLM is
  instructed to caveat them.
