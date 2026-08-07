#!/usr/bin/env python3
"""Validate every knowledge/records/*.json against its schema.

Enforces the plan-knowledge.md acceptance criteria:

- every record satisfies its per-file schema (which extends envelope.schema.json)
- every non-bibliography record has non-empty citations[]
- every citation id resolves to a record in bibliography.json
- every era_bounds entry is [iso-date-or-null, iso-date-or-null]

Run manually or wire into CI. Requires `jsonschema` (already a pyproject
dependency of hackrf_agent).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft7Validator, RefResolver
except ImportError:
    print("ERROR: jsonschema is not installed. `pip install jsonschema`.", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = REPO_ROOT / "knowledge" / "records"
SCHEMAS_DIR = REPO_ROOT / "schemas" / "knowledge"

# Map each record file to its schema file (relative to schemas/knowledge/)
FILES_TO_SCHEMAS = {
    "bibliography.json": "bibliography.schema.json",
    "bands.json": "bands.schema.json",
    "modulations.json": "modulations.schema.json",
    "protocols.json": "protocols.schema.json",
    "iq_formats.json": "iq_formats.schema.json",
    "decoders.json": "decoders.schema.json",
    "symbol_encodings.json": "symbol_encodings.schema.json",
    "fec_codes.json": "fec_codes.schema.json",
    "crypto_in_rf.json": "crypto_in_rf.schema.json",
    "keyfobs.json": "keyfobs.schema.json",
    "sdr_hardware.json": "sdr_hardware.schema.json",
    "sdr_tools.json": "sdr_tools.schema.json",
    "known_signals.json": "known_signals.schema.json",
    "dsp_concepts.json": "dsp_concepts.schema.json",
    "regulatory.json": "regulatory.schema.json",
    "antennas.json": "antennas.schema.json",
    "defense_and_detection.json": "defense_and_detection.schema.json",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_resolver() -> RefResolver:
    """Build a RefResolver that resolves $ref by loading files from SCHEMAS_DIR."""
    envelope = load_json(SCHEMAS_DIR / "envelope.schema.json")
    store = {
        "envelope.schema.json": envelope,
    }
    for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
        store[schema_file.name] = load_json(schema_file)
    # base_uri isn't actually used since our $refs are bare filenames
    return RefResolver.from_schema(envelope, store=store)


def check_citations(records: list[dict], bib_ids: set[str], file_name: str) -> list[str]:
    """Return a list of error strings for missing/unresolved citations."""
    errors = []
    for rec in records:
        rid = rec.get("id", "<no-id>")
        cites = rec.get("citations", [])
        if file_name != "bibliography.json" and not cites:
            errors.append(f"  {file_name}::{rid}: empty citations[]")
            continue
        for cite in cites:
            if cite not in bib_ids:
                errors.append(f"  {file_name}::{rid}: citation '{cite}' does not resolve to bibliography.json")
    return errors


def main() -> int:
    resolver = build_resolver()
    bib_records = load_json(RECORDS_DIR / "bibliography.json")
    bib_ids = {r["id"] for r in bib_records}

    all_errors: list[str] = []
    total_records = 0

    for file_name, schema_name in FILES_TO_SCHEMAS.items():
        record_path = RECORDS_DIR / file_name
        schema_path = SCHEMAS_DIR / schema_name

        if not record_path.exists():
            all_errors.append(f"  MISSING FILE: {file_name}")
            continue

        records = load_json(record_path)
        schema = load_json(schema_path)
        validator = Draft7Validator(schema, resolver=resolver)

        for err in validator.iter_errors(records):
            path = ".".join(str(p) for p in err.absolute_path)
            all_errors.append(f"  {file_name}::{path}: {err.message}")

        all_errors.extend(check_citations(records, bib_ids, file_name))
        total_records += len(records)

    if all_errors:
        print(f"FAIL: {len(all_errors)} validation issue(s) across {total_records} records:")
        for err in all_errors:
            print(err)
        return 1

    print(f"PASS: {total_records} records across {len(FILES_TO_SCHEMAS)} files validate cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
