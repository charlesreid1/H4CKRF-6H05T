# knowledge/records/ — typed knowledge repo

JSON records shape the "numbers live here" half of the corpus. Each file in
this directory is a JSON array of records with a shared envelope; the
knowledge-retrieval MCP verbs (`knowledge_lookup_band`,
`knowledge_lookup_modulation`, `knowledge_lookup_protocol`, …) load these
files at runtime and return records verbatim.

The authoritative machine-readable schemas live in
[`schemas/knowledge/`](../../schemas/knowledge/); the validator that
runs on every push is `scripts/validate_knowledge_records.py`. This
README documents the shared envelope and the per-file record types.

## Envelope

Every record carries:

```jsonc
{
  "id": "kebab-case-slug-unique-within-file",
  "name": "Human name",
  "aliases": ["Alternate", "Names"],
  "category": "band_allocation | modulation_family | protocol_phy | ...",
  "region": "universal | US | EU | JP | ...",
  "era_bounds": ["1980-01-01", null],   // [first_effective, last_effective]
  "still_effective_2026": true,          // required on attack/protocol records
  "confidence": "primary | secondary | community | folklore",
  "citations": ["bib-id", "..."],       // must be non-empty → bibliography.json
  "see_also": ["other-record-id"],
  "disputed": { "field": "why disputed + competing values" },  // optional
  "technical_body": { /* per-record-type fields */ },
  "hackrf_role": "rx | tx | analyze | out-of-scope | rx-primary-tx-grant-required",
  "blocked_tx": false,                   // mirrors, does NOT drive, RiskAssessor
  "tools_upstream": ["numpy", "gnuradio"],
  "tools_downstream": ["urh", "rtl_433", "multimon-ng"]
}
```

Notable rules:

- `citations` must be non-empty; every entry resolves to
  `bibliography.json`.
- `confidence`: `primary` (IEEE/ITU/FCC/vendor spec) > `secondary`
  (DEFCON talk with released code, USENIX paper) > `community` (blog,
  GitHub README, wiki) > `folklore` (unverified claim, tribal
  knowledge). Records at `folklore` confidence are still returned but
  flagged, and the LLM is instructed to caveat them.
- `blocked_tx` on `band_allocation` records mirrors — does not
  authoritatively drive — the hardcoded BLOCKED table in
  `RiskAssessor`. The gate never reads this file.
- `still_effective_2026` on attack/protocol records distinguishes "this
  technique is gone" from "this technique still works where the
  target survives."

## Files

- `bands.json` — allocated bands (`band_allocation`).
- `modulations.json` — modulation families (`modulation_family`).
- `symbol_encodings.json` — line codings (`symbol_encoding`).
- `protocols.json` — RF protocols (`protocol_phy`).
- `iq_formats.json` — capture container formats (`iq_format`).
- `decoders.json` — decoder families (`decoder_family`).
- `fec_codes.json` — CRC/Hamming/BCH/RS (`fec_code`).
- `crypto_in_rf.json` — Keeloq, HITAG2, GSM A5/*, TETRA TEA*
  (`crypto_in_rf`).
- `keyfobs.json` — keyfob systems (`keyfob_system`).
- `sdr_hardware.json` — HackRF, RTL-SDR, Airspy, LimeSDR, USRP,
  PlutoSDR, KrakenSDR (`sdr_hardware`).
- `sdr_tools.json` — GNU Radio, URH, Inspectrum, rtl_433, multimon-ng,
  dump1090, gqrx, CubicSDR (`sdr_tool`).
- `known_signals.json` — canonical signals at known frequencies,
  the recognition-tool backbone (`protocol_phy`).
- `dsp_concepts.json` — Nyquist, aliasing, IQ, filter families
  (`dsp_concept`).
- `regulatory.json` — Part 15/22/24/…/97 rule summaries
  (`regulatory`). **Documentation only** — `RiskAssessor` does not
  read this file.
- `antennas.json` — dipole/monopole/Yagi/biquad/log-periodic/discone/
  patch/helical/whip (`antenna`).
- `defense_and_detection.json` — RF hygiene, rogue detection
  (`defense_and_detection`).
- `bibliography.json` — sources with pinpoint cites (`bibliography`).

## Loader contract

- Files are read fresh on every MCP process start; no per-session
  persistence.
- Path traversal is denied at the handler boundary. Records reference
  each other by `id`; free-text search is a separate verb
  (`knowledge_search`).
- Missing `citations` is a hard validation error. Missing `disputed`
  is fine (most records don't have one).
- `confidence: folklore` records are returned but flagged.
