# regulatory/reference.md — the rulebook that shapes the BLOCKED table

Machine-readable version lives in `../records/regulatory.json`. This
file is the prose version. **Neither this file nor the JSON can override
the hardcoded `RiskAssessor` BLOCKED table** — that coupling is
explicitly forbidden by `../../plan-organization.md` Phase 6.

## FCC Part 15 — unlicensed low-power

The heart of hobby RF in the US.

- **§15.231 — periodic transmitters (315 MHz, 433 MHz).** Max field
  strength: 12,500 μV/m at 3 m at 433 MHz (~35 nW EIRP). Duty cycle
  limits apply. Covers most keyfobs, garage doors, TPMS. Legal to TX
  with a HackRF only if you stay under the field-strength limit —
  hard at high VGA.
- **§15.247 — spread-spectrum (902–928 MHz, 2400–2483.5 MHz,
  5725–5850 MHz).** 1 W max output, plus antenna-gain rules. Covers
  WiFi, Bluetooth, most 900/2.4 GHz LPWAN.
- **§15.249 — narrowband, same bands.** 10 mW EIRP (nominally).
  Covers narrowband ISM devices.

## FCC Part 97 — amateur radio

Requires an FCC license (Technician / General / Extra). Grants
operating privileges in specific amateur bands with mode + power caps
by band + class. Key amateur bands the HackRF can reach:

- 6 m (50–54 MHz)
- 2 m (144–148 MHz)
- 1.25 m (222–225 MHz)
- 70 cm (420–450 MHz — overlaps EU ISM 433 !)
- 33 cm (902–928 MHz — overlaps US ISM 902–928)
- 23 cm (1240–1300 MHz)
- 13 cm (2300–2450 MHz)
- 9 cm (3300–3500 MHz)
- 5 cm (5650–5925 MHz)

**Overlaps matter.** 70 cm amateur is 420–450 MHz; EU 433 ISM sits
inside it. In the US, transmitting at 433.92 MHz is Part 15 §15.231
if you're a keyfob, or Part 97 if you're a licensed ham; the same
frequency, two different regulatory frames.

## FCC Part 87 — aviation

**118–137 MHz** aviation voice. **BLOCKED for TX** in the
RiskAssessor. Includes VHF Guard 121.5 MHz (international
aeronautical emergency).

## FCC Part 80 — maritime

**156.7625–156.8375 MHz** maritime distress/safety (channel 16 +
DSC). **BLOCKED for TX.** The rest of marine VHF (156–162 MHz) is
RX-only by default in this MCP.

## FCC Part 22 / 24 / 27 — cellular

Downlink bands are **BLOCKED for TX** per the RiskAssessor. The
hardcoded ranges are Band 12 (729–746), Band 13 (746–756), Band 17
(734–746, nested inside Band 12), Band 5 (869–894), Band 2
(1930–1990), Band 4 (2110–2155). These are all "cell tower to
handset" directions — transmitting at these frequencies would
attempt to impersonate a cell tower.

## Radio astronomy protected bands

Passive-only services under ITU-R RA.769. **BLOCKED for TX** in
`RiskAssessor`:

- 406.1–410.0 MHz
- 608–614 MHz
- 1400–1427 MHz (21 cm hydrogen line)
- 2690–2700 MHz

## GNSS

**All GNSS bands are BLOCKED for TX** in `RiskAssessor`:

- GPS L1 (1559–1591 MHz)
- GPS L2 (1215–1240 MHz)
- GPS L5 safety-of-life (1164–1189 MHz)
- GLONASS G1 (1592.9–1610.5 MHz)
- GLONASS G2 (1237.8–1254.4 MHz)
- Galileo E6 (1260–1300 MHz)

## Public safety

**BLOCKED for TX** in `RiskAssessor`:

- 758–775 MHz — FirstNet (public safety narrow/broadband)
- 851–854 MHz — NPSPAC (Part 90)

## ITU regions

Region 1 (Europe, Middle East, Africa), Region 2 (Americas),
Region 3 (Asia/Pacific). Consequences:

- **433 MHz** is EU ISM (Region 1) but amateur secondary in the US
  (Region 2).
- **868 MHz** is EU ISM but part of US cellular downlink (Region 2).
- **915 MHz** is US ISM but mostly cellular in EU.

The `region` field on `bands.json` records captures which regulatory
frame a given band lives under.

## ETSI EN 300 220

The European counterpart to Part 15 §15.231. Covers 25 MHz – 1 GHz
short-range devices, per-band duty cycle limits (typically 0.1 %,
1 %, 10 % or unlimited depending on sub-band), ERP limits
(typically 10 mW).

- 433.050–434.790 MHz (SRD)
- 868.0–868.6 MHz (SRD Band a) — 25 mW, 1 % DC
- 868.7–869.2 MHz (Band b) — 25 mW, 0.1 % DC
- 869.4–869.65 MHz (Band c) — 500 mW, 10 % DC
- 869.7–870.0 MHz (Band d) — 5 mW, unlimited

## Industry Canada RSS-210

Mostly harmonized with FCC Part 15. Any RF device certified for one
market frequently works in the other with minor label changes.

## The BLOCKED table lives in code

For the authoritative list of frequencies the gate refuses, read
`src/hackrf_agent/domain/frequency_policy.py:BLOCKED_BANDS`. This
document mirrors it in prose; the file mirrors it in JSON.
`RiskAssessor` reads only the Python constant. That layering is
intentional — see Phase 6 of `../../plan-organization.md`.
