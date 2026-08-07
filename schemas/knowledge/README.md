# schemas/knowledge — JSON Schemas for the record files

Draft-07 JSON Schemas that validate each of `knowledge/records/*.json`.

## Files

- `envelope.schema.json` — the shared record envelope (id, name,
  category, era_bounds, citations, confidence, ...). Every per-file
  schema references this via `$ref`.
- `bibliography.schema.json` — `knowledge/records/bibliography.json`.
- `bands.schema.json` — `knowledge/records/bands.json`.
- `modulations.schema.json` — `knowledge/records/modulations.json`.
- `protocols.schema.json` — `knowledge/records/protocols.json`.
- `iq_formats.schema.json` — `knowledge/records/iq_formats.json`.
- `decoders.schema.json` — `knowledge/records/decoders.json`.
- `symbol_encodings.schema.json` — `records/symbol_encodings.json`.
- `fec_codes.schema.json` — `records/fec_codes.json`.
- `crypto_in_rf.schema.json` — `records/crypto_in_rf.json`.
- `keyfobs.schema.json` — `records/keyfobs.json`.
- `sdr_hardware.schema.json` — `records/sdr_hardware.json`.
- `sdr_tools.schema.json` — `records/sdr_tools.json`.
- `known_signals.schema.json` — `records/known_signals.json`.
- `dsp_concepts.schema.json` — `records/dsp_concepts.json`.
- `regulatory.schema.json` — `records/regulatory.json`.
- `antennas.schema.json` — `records/antennas.json`.
- `defense_and_detection.schema.json` — `records/defense_and_detection.json`.

## Validation

`scripts/validate_knowledge_records.py` runs every record file against
its schema and asserts:

- Every record has a non-empty `citations[]` (except bibliography
  records themselves).
- Every citation id resolves to a record in `bibliography.json`.
- Every `era_bounds` is `[iso-date-or-null, iso-date-or-null]`.
- Every `confidence` is one of `primary | secondary | community |
  folklore`.

The plan is to wire this into CI once the schemas stabilize.
