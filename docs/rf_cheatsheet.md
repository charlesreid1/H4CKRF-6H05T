# RF CHEATSHEET

The one-page "everything I want to be able to answer in five seconds"
reference. Placeholder — grows as we play. Numbers-authoritative content
lives in `knowledge/records/*.json`; this file is the fast-lookup surface.

## Band-at-a-glance

| Band             | Center      | Usual denizens             | H4CKRF verdict |
|------------------|-------------|----------------------------|----------------|
| ISM 315 MHz      | 315.000     | NA keyfobs, TPM, garage    | RX/TX ok       |
| ISM 433 MHz      | 433.920     | EU keyfobs, weather, garage| RX/TX ok       |
| ISM 868 MHz      | 868.300     | EU LPWAN, Z-Wave (EU)      | RX/TX ok       |
| ISM 915 MHz      | 915.000     | US LPWAN, LoRa (US), Z-Wave| RX only default|
| Airband voice    | 118–137     | ATC, ATIS                  | BLOCKED (TX)   |
| Marine VHF       | 156–162     | AIS, maritime voice        | BLOCKED (TX)   |
| ADS-B            | 1090        | aircraft transponders      | BLOCKED (TX)   |
| GPS L1 / L2      | 1575 / 1227 | GNSS                       | BLOCKED (TX)   |
| Cellular DL      | many        | LTE/5G downlink            | BLOCKED (TX)   |

## Modulation-at-a-glance

- ASK/OOK — envelope changes; classic keyfob PHY
- FSK — two-tone; POCSAG, most modern keyfobs
- GFSK — Gaussian-filtered FSK; Bluetooth PHY, many LPWANs
- MSK/GMSK — 1-bit-per-symbol phase modulation; GSM DL
- PSK — phase; BPSK/QPSK/8PSK
- QAM — amplitude+phase; every high-throughput link

## Keyfob / TPM / weather cheat lines

- Fixed-code OOK (early garage doors, some TPMs) — replay works
- Rolling-code Keeloq (Chamberlain, HCS) — replay defeated by counter
- KeeLoq HITAG2 — proprietary crypto; timing side-channel research
- Manchester encoding at 433.92 MHz, ~2 kbps — 99% of "did you decode
  a keyfob today" questions

## The first-60-seconds triage table

See [ctf_playbook.md](ctf_playbook.md).
