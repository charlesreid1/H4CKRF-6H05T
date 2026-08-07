# regulatory/

FCC Part 15 §15.231 (315 MHz), §15.247/§15.249 (2.4 GHz), ISM band table,
Part 97 (amateur), plus why each BLOCKED band is blocked (ADS-B, GPS,
aviation voice, marine distress, cellular downlink, emergency services).

The machine-readable version lives in `records/regulatory.json`.
**Reminder:** `RiskAssessor` never reads that file — the BLOCKED table
stays hardcoded in Python. This is intentional: coupling the gate to
editable JSON would be a bypass; the split keeps the enforcement path
short and auditable.
