# knowledge/ — the H4CKRF-6H05T RF/SIGINT corpus

This directory is the *reference* half of H4CKRF-6H05T. The MCP server in
`src/hackrf_agent/` is the *acting* half; the safety funnel between them is
described in [../plan-organization.md](../plan-organization.md).

The corpus is data, not code. It is read at runtime by the knowledge
handlers in `hackrf_agent.domain.handlers` from a canonical path resolved
via `SessionPaths` (with an env-var override for dev). It is not shipped
as `package_data`.

## What this corpus is for

An RF co-pilot needs to know the canon before it acts. The MCP tools that
back this corpus (see Phase 3 of `../plan-organization.md`) let the assistant
answer questions like "what's on 433.92 MHz?" or "is this an OOK keyfob?"
from files on disk instead of from model weights. That matters because model
weights are unaccountable and out of date; the corpus is cited, versioned,
and reviewable in a PR.

## How files are exposed

Every markdown file becomes an MCP resource under
`hackrf://knowledge/<topic>/<name>`. Every JSON record file under
`knowledge/records/` is retrievable via a `knowledge_lookup_*` verb bound to
the corresponding record type (see `knowledge/records/README.md` for the
record schema). Free-text search is available via `knowledge_search`; typed
lookups are preferred whenever a `knowledge_lookup_*` verb exists.

## Retrieval discipline

- Numbers live in `records/*.json`. Prose lives in `<topic>/*.md`.
- Retrieval tools bind to records, not to free text.
- Every record cites a source (see `records/bibliography.json` when it lands).
- Every claim carries `era_bounds`, `region`, and `confidence` in
  `{primary, secondary, community, folklore}`.
- The BLOCKED band table stays hardcoded in `RiskAssessor`. The
  `records/regulatory.json` file is *documentation*, not configuration
  — the gate never reads it. See Phase 6 of `../plan-organization.md`.

## Per-topic file convention

Each `<topic>/` ships up to four files:

- `README.md` — orient. What is this, why care. Short.
- `reference.md` — the technical spec. Freqs, bandwidths, framings,
  symbol rates, standards citations. Numbers-dense.
- `walkthrough.md` — one or more worked examples with real waterfall hints
  ("you see a 20 kHz OOK spike at 433.92, Manchester-encoded, 2 kbps —
  probably a keyfob").
- `recognition.md` — how to identify this thing from a spectrogram or a
  capture summary in the wild. For H4CKRF this is the load-bearing file
  per topic.
- `history.md` — optional. Full story, sources, incidents.

Not every topic earns all five; author the split as the topic warrants.

## Topics — seed list

Tier 1 — Foundations (write first):

- `dsp/` — IQ representation, sample rate, decimation, FFT windowing,
  spectrograms, filter design basics.
- `sdr-fundamentals/` — Nyquist, aliasing, IQ imbalance, DC spike,
  gain staging, ADC quantization, `target_freq_hz` vs `center_freq_hz`.
- `modulation/` — AM, FM, SSB, ASK, OOK, FSK, GFSK, MSK, GMSK, PSK, QAM,
  OFDM. Spectral signatures + canonical uses.
- `hackrf-hardware/` — MAX2837/RFFC5072 chipset, split TX/RX architecture,
  half-duplex, 8-bit ADC and its dynamic-range implications.
- `iq-formats/` — `.iq`, `.cf32`, `.cs8`, `.cs16`, SigMF metadata.
- `regulatory/` — FCC Part 15 §15.231, §15.247, §15.249, ISM band table,
  Part 97, plus why each BLOCKED band is blocked.

Tier 2 — Common bands and signals (write next):

- `ism-315/` — NA keyfobs, TPMS, some garage doors.
- `ism-433/` — EU ISM, weather stations, keyfobs, garage doors, EU TPMS.
- `ism-868-915/` — EU 868 / US 915 LPWAN, LoRa, Z-Wave, Sigfox.
- `ism-2400/` — Bluetooth Classic + BLE (observation only), Zigbee.
- `ads-b/` — Mode S extended squitter at 1090 MHz. **RX-only.**
- `pocsag-flex/` — POCSAG 512/1200/2400 and FLEX paging.
- `aprs/` — Automatic Packet Reporting System (AX.25 over Bell 202
  AFSK-1200); paired with the `decode_aprs` MCP verb.
- `keyfobs/` — fixed vs rolling, Keeloq, HITAG2, Passive Keyless Entry.
- `garage-doors/` — Genie, Chamberlain, LiftMaster generations.
- `weather-stations/` — Acurite, Fine Offset, La Crosse, Oregon Scientific.
- `tpm/` — TPMS PHY notes and per-vendor framing.
- `lora/` — LoRa PHY, spreading factors, LoRaWAN framing.
- `zigbee-802154/` — 802.15.4 PHY, MAC framing, channels 11–26.
- `dmr/`, `tetra/`, `p25/` — digital voice trunking. RX-only unless licensed.
- `airband/` — 118–137 MHz AM aviation voice. **BLOCKED for TX.**
- `marine-vhf-ais/` — 156–162 MHz, AIS at 161.975/162.025.
- `satellite/` — NOAA APT, GOES HRIT, Iridium, ISS voice, GPS L1 (RX-only).

Tier 3 — Analysis and decoders:

- `iq-analysis/` — waterfall reading, symbol-timing recovery, SNR
  estimation.
- `demodulators/` — AM/FM/OOK/FSK/PSK demod pipelines in numpy prose.
- `decoders/` — Manchester, differential Manchester, NRZ, NRZI, PWM,
  PPM, PCM.
- `crc-fec/` — CRC-8/16, common preambles, Reed-Solomon in POCSAG,
  Hamming.
- `crypto-in-rf/` — Keeloq (NLFSR), HITAG2, rolling counters vs replay.

Tier 4 — CTF-facing:

- `ctf/` — one file per subgenre: `rf-triage`, `spectrogram-reading`,
  `unknown-keyfob`, `replay-vs-analyze`, `waterfall-stego`, `packet-flag`,
  `two-tone-cipher`, `numbers-station-decode`, `paging-decode`,
  `ads-b-recon`.

Every topic dir ships an empty `README.md` at repo skeleton time so the
`knowledge_list_topics` MCP verb discovers the structure on day one, even
before the walkthroughs are written.
