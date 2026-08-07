# history/reference.md — timeline

## Pre-SDR (context)

- **1897** — Marconi's first patents; RF engineering as a formal
  discipline begins.
- **1930s** — commercial AM broadcast reaches saturation; VHF/UHF
  experiment stations begin.
- **1948** — Shannon publishes *A Mathematical Theory of Communication*.
  Digital comms starts.
- **1962** — first geostationary comms sat (Telstar).

## SDR — from research to commodity

- **1979** — MIT's Cooley-Tukey FFT lineage matures. Early software
  demodulators appear in academia.
- **2001** — Eric Blossom starts GNU Radio. Free software for signal
  processing suddenly viable on commodity PCs.
- **2007** — USRP1 ships. GNU Radio 3.0. SDR at ~$1000.
- **2009** — Osmocom starts (Harald Welte). GSM tooling begins with
  OpenBTS + OsmoBTS lineage.
- **2012** — Michael Ossmann's HackRF Jawbreaker Kickstarter succeeds.
- **2013** — Antti Palosaari discovers the RTL-SDR can be turned into
  an SDR receiver via the DVB-T dongle mode. rtl-sdr and rtl_433
  begin. SDR at $20.
- **2014** — HackRF One ships to backers. PortaPack H1 (community
  add-on) begins. HackRF documentation on hackrf.readthedocs.io.
- **2015** — Samy Kamkar's RollJam disclosure at DEF CON 23. Jams the
  keyfob receiver during press N, records the press, plays it back
  later. Class of jam-record-replay attacks.

## Automotive RF security

- **2005** — Bono/Green/Stubblefield disclose TI DST40 cipher recovery
  (ExxonMobil SpeedPass demo).
- **2008** — Kasper/Eisenbarth/Moradi/Paar publish the Keeloq slide
  attack (CHES 2008). Learn-mode key recovery via power analysis.
- **2010** — Rouf et al. disclose TPMS spoofing and privacy
  vulnerabilities (USENIX Security).
- **2011** — Francillon/Danev/Capkun disclose PKE relay attacks
  (NDSS). Two-attacker relay of the "fob is near the car" signal
  works against every PKE system in the wild.
- **2012** — Verdult/Garcia/Balasch "Gone in 360 Seconds" — HITAG2
  key recovery (USENIX Security).
- **2013** — Verdult/Garcia/Ege "Dismantling Megamos Crypto"
  (USENIX Security). VW group's injunction delays publication until
  2015.
- **2022** — Csikor et al. "RollBack" (Black Hat USA) — counter-rewind
  acceptance in some vehicles.
- **2022** — Kevin2600/Wesley Li "Rolling PWN" (CVE-2022-27254). Honda
  Civic/CR-V/Accord subset accept rewound counters.

## Digital voice trunking

- **1995** — TIA/EIA-102 (P25 Phase 1) standardized in the US.
- **1995** — ETSI EN 300 392 (TETRA) standardized in EU.
- **2005** — ETSI TS 102 361 (DMR) standardized.
- **2013** — Balint Seeber's "Hacking the Wireless World with SDR"
  (Black Hat 2013).
- **2016** — Iridium Toolkit disclosed at Sec-T. `gr-iridium` and
  `iridium-toolkit` publish. Iridium's L-band downlink shown to be
  observable with commodity SDR.
- **2023** — Midnight Blue's TETRA:BURST (five CVEs in TETRA
  air-interface encryption). TEA1 shown to have a 32-bit effective
  key despite 80-bit nominal.

## WiFi (P1N3NUT5 territory; cross-references only)

- **2001** — WEP broken (Fluhrer/Mantin/Shamir).
- **2017** — KRACK (Vanhoef).
- **2018** — Steube's PMKID.
- **2019-2024** — Vanhoef research (Kr00k, Dragonblood, FragAttacks,
  etc.).

## HackRF ecosystem

- **2016** — HackRF PortaPack H2 (Havoc firmware).
- **2019** — SDR++ development begins (Alexandre Rouma).
- **2021** — SatDump initial release.
- **2022** — Great Scott Gadgets ships firmware major update
  supporting bidirectional Opera Cake.
- **2024** — HackRF PortaPack H4 with dual-radio support.

## Standards + cultural moments

- **2000** — SigMF working group begins (community metadata for IQ
  captures).
- **2015** — DEF CON RF Village becomes a distinct village.
- **2018** — SigMF v1.0 published.
- **2020** — GNU Radio 3.8 → 3.9 → 3.10 transitions; QT-based GRC
  becomes default.
