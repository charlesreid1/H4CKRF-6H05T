# bibliography/reference.md — the sources

The machine-readable list is `../records/bibliography.json`. This file
is the human-oriented overview.

## Priority ordering

- **Primary:** IEEE / ITU / FCC / ETSI / vendor spec.
- **Secondary:** peer-reviewed research (USENIX Security, NDSS, CHES,
  IEEE S&P), DEF CON / Black Hat talks *with released code*.
- **Community:** high-quality blog write-ups, GitHub repositories,
  community wikis.
- **Folklore:** unverified tribal knowledge. Cited but flagged.

Every record must resolve at least one primary or secondary source
where possible. Community-only records are OK for niche topics but
should note the limitation.

## Books (canonical)

- **Steven W. Smith, *The Scientist and Engineer's Guide to Digital
  Signal Processing*** (1997, free at dspguide.com). The DSP primer.
  Use for anything about FFTs, filters, spectra.
- **Oppenheim & Schafer, *Discrete-Time Signal Processing*** (3rd ed.,
  2010). Graduate DSP. Use for advanced filter theory, cyclostationary
  analysis, adaptive filtering.
- **Proakis & Salehi, *Digital Communications*** (5th ed., 2007). The
  digital-comm bible. Use for modulation theory, symbol timing,
  matched filtering, FEC.
- **Rice, *Digital Communications: A Discrete-Time Approach*** (2008).
  Approachable coverage of carrier/timing recovery, RRC.
- **Sklar, *Digital Communications: Fundamentals and Applications***
  (2nd ed., 2001). Alternative to Proakis.
- **Viterbi, *Principles of Coherent Communication*** (1966). Historical
  primary source for the Viterbi algorithm.

## Standards + regulatory

- **FCC 47 CFR Part 15** — unlicensed operation. Includes §15.231
  (315 MHz keyfobs), §15.247 (spread-spectrum in 902-928/2400-2483.5),
  §15.249 (narrowband). ecfr.gov current text.
- **FCC 47 CFR Part 87** — aviation (BLOCKED for TX in this MCP).
- **FCC 47 CFR Part 97** — amateur radio.
- **ETSI EN 300 220** — EU SRD 25-1000 MHz.
- **ETSI EN 300 328** — EU 2.4 GHz wideband transmission.
- **ETSI TS 102 361** — DMR air interface.
- **ETSI EN 300 392** — TETRA air interface.
- **ITU-R M.584-2** — POCSAG paging.
- **ITU Radio Regulations** — the treaty framework.
- **RTCA DO-260B** — ADS-B Mode S Extended Squitter MOPS.
- **IEEE 802.15.4** — Zigbee PHY/MAC.
- **IEEE 802.11** — WiFi (P1N3NUT5 territory but referenced here).
- **LoRaWAN 1.0.4 / 1.1** — LoRa Alliance specifications.
- **SigMF v1.0** — signal metadata format.

## Research papers (recurring citations)

- **Kamkar 2015** (DEF CON 23) — RollJam.
- **Kevin2600 + Wesley Li 2022** — Rolling PWN (CVE-2022-27254).
- **Csikor et al. 2022** — RollBack (Black Hat USA).
- **Kasper/Eisenbarth/Moradi/Paar 2008** — Keeloq slide attack (CHES).
- **Verdult/Garcia/Balasch 2012** — HITAG2 (USENIX Security).
- **Verdult/Garcia/Ege 2013/2015** — Megamos Crypto (USENIX Security).
- **Francillon/Danev/Capkun 2011** — PKE relay attacks (NDSS).
- **Rouf et al. 2010** — TPMS vulnerabilities (USENIX Security).
- **Midnight Blue 2023** — TETRA:BURST.
- **Sec-T 2016** — Iridium Toolkit.

## Software / repos (recurring)

- **GNU Radio wiki** — the block reference.
- **Osmocom wiki** — rtl_sdr, OpenBTS, GSM tooling.
- **HackRF GitHub** (greatscottgadgets/hackrf) — firmware + host tools.
- **URH GitHub** (jopohl/urh).
- **rtl_433 GitHub** (merbanan/rtl_433).
- **multimon-ng GitHub** (EliasOenal/multimon-ng).
- **dump1090 / readsb GitHub** (wiedehopf/readsb is the maintained
  fork).
- **Inspectrum GitHub** (miek/inspectrum).
- **SigDigger GitHub** (BatchDrake/SigDigger).
- **SatDump GitHub** (SatDump/SatDump).
- **iridium-toolkit + gr-iridium** (muccc).

## Video / conference archives

- **Michael Ossmann, *Software Defined Radio with HackRF*** — the
  canonical SDR primer from the HackRF's creator. Free on YouTube;
  the recommended first-week study.
- **DEF CON RF Village archives** — talk recordings and slides,
  2014-present.
- **RTL-SDR blog** (rtl-sdr.com) — wide-audience SDR project write-ups;
  community-tier confidence but often research-grade content.
- **Sig ID Wiki** (sigidwiki.com) — community-maintained catalog of
  "what is this signal?" — useful reference for recognition.md
  material.

## Discipline

- Every `reference.md` cites at least one primary source at the
  bottom. No primary cite → the record does not load. Enforced by
  `scripts/validate_knowledge_records.py` and the machine-readable
  schemas under `schemas/knowledge/`.
- Community-tier citations are OK for records tagged
  `confidence: community` or `confidence: folklore`, but the record
  itself must note the limitation.
- Folklore records are returned but flagged; the assistant is
  instructed to caveat them.
