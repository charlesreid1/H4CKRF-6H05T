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
- Every record cites a source; every citation resolves to
  `records/bibliography.json` (enforced by
  `scripts/validate_knowledge_records.py`).
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

## Cheatsheet

See `cheatsheet.md` — the single densest page. Everything an operator
would want to memorize plus a jump-off to the per-topic files.

## Topics

### Tier 1 — Foundations

- `dsp/` — IQ representation, sample rate, decimation, FFT windowing,
  spectrograms, filter design basics.
- `sdr-fundamentals/` — Nyquist, aliasing, IQ imbalance, DC spike,
  gain staging, ADC quantization, `target_freq_hz` vs `center_freq_hz`.
- `hackrf-hardware/` — MAX2837/RFFC5072 chipset, split TX/RX
  architecture, half-duplex, 8-bit ADC.
- `iq-formats/` — `.iq`, `.cs8`, `.cu8`, `.cs16`, `.cf32`, WAV, SigMF.
- `regulatory/` — FCC Part 15 §15.231, §15.247, §15.249, ISM band table,
  Part 97, plus why each BLOCKED band is blocked.

### Tier 2 — Modulation

- `modulation/` — umbrella + at-a-glance table.
- `modulation/am-fm-ssb/` — analog modulation.
- `modulation/ask-ook/` — 315/433 MHz keyfob PHY family.
- `modulation/fsk-gfsk-msk-gmsk/` — POCSAG, BLE, GSM, AIS, DMR PHYs.
- `modulation/psk-qam/` — satellite downlinks, TETRA.
- `modulation/ofdm/` — WiFi, LTE, DVB-T, DAB, 5G.
- `modulation/lora-css/` — LoRa chirp spread spectrum.
- `modulation/dsss-fhss/` — GPS L1 C/A, older WiFi, Bluetooth Classic.

### Tier 3 — Common bands and signals

- `ism-315/`, `ism-433/`, `ism-868-915/`, `ism-2400/` — the sub-GHz
  and 2.4 GHz clusters.
- `ads-b/` — Mode S at 1090 MHz. **RX only.**
- `pocsag-flex/` — POCSAG 512/1200/2400 and FLEX paging.
- `aprs/` — AX.25 over Bell 202 AFSK-1200.
- `keyfobs/`, `garage-doors/` — fixed / rolling / crypto-rolling.
- `weather-stations/` — Acurite, Fine Offset, La Crosse, Oregon
  Scientific.
- `tpm/` — TPMS PHY notes.
- `lora/` — LoRa PHY + LoRaWAN framing.
- `zigbee-802154/` — 802.15.4 PHY.
- `dmr/`, `tetra/`, `p25/` — digital voice trunking.
- `airband/` — 118-137 MHz AM. **BLOCKED for TX.**
- `marine-vhf-ais/` — 156-162 MHz + AIS at 161.975/162.025.
- `satellite/` — NOAA APT, GOES HRIT, Iridium, ISS voice, GPS L1
  (RX-only).

### Tier 4 — Analysis, decoders, tool chain

- `iq-analysis/` — waterfall reading, symbol-timing recovery, SNR.
- `demodulators/` — AM/FM/OOK/FSK/PSK numpy demod pipelines.
- `decoders/` — Manchester, differential Manchester, NRZ, NRZI, PWM,
  PPM, PCM.
- `crc-fec/` — CRC-8/16, Hamming, BCH, Reed-Solomon.
- `crypto-in-rf/` — Keeloq, HITAG2, rolling counters vs replay.
- `gnu-radio-primer/` — block model + three canonical flowgraphs.
- `urh/` — the four panes (signal / analysis / generation / simulator).
- `inspectrum/` — precision cursor tool.
- `rtl-433/` — sub-GHz catalog decoder.
- `multimon-ng/` — audio-side legacy decoder.
- `dump1090-readsb/` — ADS-B decoder.
- `gqrx-cubicsdr-sdrpp/` — GUI receivers.
- `hackrf-transfer-and-sweep/` — vendor CLI.
- `sigmf-metadata/` — community IQ container format.
- `signal-generation-with-numpy/` — upstream side (generate IQ files).
- `transmit-pipeline/` — downstream side (safety-gated `transmit_iq`).
- `antennas/` — dipole, monopole, Yagi, biquad, patch, discone.

### Tier 5 — CTF-facing

- `ctf/rf-triage.md`, `spectrogram-reading.md`, `signal-classification.md`
- `ctf/unknown-keyfob.md`, `garage-door-forensics.md`,
  `weather-station-flag.md`, `replay-vs-analyze.md`
- `ctf/lora-flag.md`, `frequency-hop-flag.md`
- `ctf/ads-b-recon.md`, `paging-decode.md`
- `ctf/waterfall-stego.md`, `spectrum-map-flag.md`,
  `two-tone-cipher.md`, `numbers-station-decode.md`
- `ctf/packet-flag.md`, `crc-audit.md`, `whitening-audit.md`

### Tier 6 — Closing coverage

- `history/` — chronological timeline of SDR + automotive RF security +
  digital voice trunking + HackRF ecosystem milestones.
- `glossary/` — every recurring acronym in the corpus.
- `bibliography/` — prose companion to `records/bibliography.json`.

Every topic dir ships at least a `README.md` so `knowledge_list_topics`
discovers the structure on day one.
