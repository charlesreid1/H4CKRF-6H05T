# RF CHEATSHEET

The one-page "everything I want to be able to answer in five seconds"
reference. Numbers-authoritative content lives in
`knowledge/records/*.json`; this file is the fast-lookup surface.

## Band-at-a-glance

| Band             | Center      | Usual denizens             | H4CKRF verdict |
|------------------|-------------|----------------------------|----------------|
| ISM 315 MHz      | 315.000     | NA keyfobs, TPMS, garage   | RX/TX ok       |
| ISM 433 MHz      | 433.920     | EU keyfobs, weather, garage| RX/TX ok       |
| ISM 868 MHz      | 868.300     | EU LPWAN, LoRa, Z-Wave (EU)| RX/TX ok       |
| ISM 915 MHz      | 915.000     | US LPWAN, LoRa (US), Z-Wave| RX only default|
| 1.25 m / 70 cm   | 222 / 420   | amateur — HIGH tier for TX | LIC only       |
| ADS-B / SSR      | 1090        | aircraft transponders      | BLOCKED (TX)   |
| GPS L1 / L2 / L5 | 1575 / 1227 | GNSS                       | BLOCKED (TX)   |
| GLONASS G1 / G2  | 1600 / 1245 | GNSS                       | BLOCKED (TX)   |
| Galileo E6       | 1278        | GNSS                       | BLOCKED (TX)   |
| Airband voice    | 118–137     | ATC, ATIS                  | BLOCKED (TX)   |
| Marine VHF       | 156–162     | AIS, maritime voice        | BLOCKED (TX)   |
| Maritime Ch 16   | 156.8       | distress/safety            | BLOCKED (TX)   |
| Cellular DL      | many        | LTE/5G downlink            | BLOCKED (TX)   |
| Public safety    | 758–775     | FirstNet / NPSPAC          | BLOCKED (TX)   |
| Radio astronomy  | 1400–1427   | ITU-R RA.769 protected     | BLOCKED (TX)   |

Every band → `knowledge_lookup_band({freq_hz})` for the full record.

## Modulation-at-a-glance

| Family | Signature | Typical PHY |
|--------|-----------|-------------|
| OOK / ASK-2 | envelope on-off; DC-heavy | keyfobs, weather, TPMS |
| 2FSK | two spectral lines | POCSAG, RTTY, telemetry |
| GFSK | 2FSK with rounded transitions | Bluetooth, many LPWANs |
| MSK / GMSK | continuous-phase FSK, h=0.5 | GSM downlink |
| BPSK / QPSK / 8PSK | phase constellation | satellite, some LoRa |
| QAM (16, 64, 256) | amp + phase constellation | high-throughput links |
| OFDM | wide flat brick | WiFi, LTE, DVB-T |
| LoRa CSS | diagonal chirp streaks | 868/915 MHz LPWAN |

## Line-code cheatsheet

| Line code | Detects by | Where you see it |
|-----------|-----------|------------------|
| Manchester | mid-bit transition | 315/433 keyfobs, TPMS |
| Diff Manchester | polarity-tolerant Manch | some RFID, some keyfobs |
| NRZ | level = bit | POCSAG post-FSK, many demod outputs |
| NRZI | transition = one value | AX.25, USB, some RFID |
| PWM | pulse-width ratio | Chamberlain garage, IR remotes |
| PPM | pulse-position gap | Acurite weather, ADS-B (native) |

Every family → `knowledge_lookup_decoder({name})`.

## Keyfob / TPM / weather cheat lines

- **Fixed-code OOK.** Early garage doors, some TPMS — replay works.
- **Rolling-code Keeloq.** Chamberlain, HCS — replay defeated by
  counter, RollJam workaround.
- **HITAG2 immobilizer.** Proprietary crypto, USENIX 2012 attack.
  Practical to break end-to-end.
- **Manchester at 433.92 MHz, ~2 kbps.** 99% of "did you decode a
  keyfob today" questions.
- **Acurite/Fine Offset weather at 433.92 MHz.** OOK, per-vendor
  PWM/PPM variants. `rtl_433` decoder catalog is authoritative.

## Cross-references

- Every band → `knowledge/records/regulatory.json` (documentation
  only — the gate has its own hardcoded truth in
  `src/hackrf_agent/domain/frequency_policy.py`).
- Every protocol → `knowledge_lookup_protocol({name})` or the
  matching `knowledge/<topic>/` directory.
- First 60 seconds → [ctf_playbook.md](ctf_playbook.md).
- Signal recognition → `knowledge/iq-analysis/recognition.md`.
