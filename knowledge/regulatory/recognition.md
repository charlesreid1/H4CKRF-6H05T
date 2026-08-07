# regulatory/recognition.md — is this a TX puzzle or an RX puzzle?

The single most important question when you see an unfamiliar
frequency in a CTF.

## Rule of thumb

**If the target band is in the BLOCKED list, the puzzle is RX-only.**
Full stop. The flag will not require you to transmit; if it appears
to, you have misread the prompt.

## The BLOCKED list (as of `frequency_policy.py`)

- 118–137 MHz (aviation voice)
- 121.4–121.6 MHz (VHF Guard, nested in the above)
- 156.7625–156.8375 MHz (maritime distress channel 16)
- 406.1–410 MHz (radio astronomy)
- 608–614 MHz (radio astronomy)
- 729–756 MHz (cellular downlink Bands 12/13/17)
- 758–775 MHz (FirstNet public safety)
- 851–854 MHz (NPSPAC public safety)
- 869–894 MHz (cellular downlink Band 5)
- 1087–1093 MHz (ADS-B / SSR / TCAS)
- 1164–1189 MHz (GPS L5)
- 1215–1240 MHz (GPS L2)
- 1237.8–1254.4 MHz (GLONASS G2)
- 1260–1300 MHz (Galileo E6)
- 1400–1427 MHz (radio astronomy 21 cm)
- 1559–1591 MHz (GPS L1)
- 1592.9–1610.5 MHz (GLONASS G1)
- 1930–1990 MHz (cellular downlink Band 2)
- 2110–2155 MHz (cellular downlink Band 4)
- 2690–2700 MHz (radio astronomy)

## The obvious "TX-ok with a grant" bands

- 315 MHz (ISM, Part 15 §15.231, tight power limits)
- 433.05–434.79 MHz (EU ISM, ETSI EN 300 220 — Region 1)
- 868 / 902–928 MHz (LPWAN / LoRa; region-dependent)
- 2400–2483.5 MHz (2.4 GHz ISM, WiFi/BT/Zigbee — but shared)
- 5725–5850 MHz (5 GHz ISM)

Plus amateur bands if the operator is licensed.

## Recognition table

| Sighting | RX-only clue? | TX-legit clue? |
|----------|---------------|----------------|
| 1090 MHz ADS-B frames | ✔ RX-only. TX would jam air traffic. | never |
| 156.8 MHz DSC bursts | ✔ maritime distress; RX only. | never |
| 118–137 MHz AM voice | ✔ airband; RX only. | never |
| 433.92 MHz OOK bursts | maybe — replay research is common | with grant + owner consent + local rules |
| 900 MHz LoRa uplinks | RX to observe; TX only under 902–928 US ISM with §15.247 compliance | with grant |
| 137 MHz NOAA APT | ✔ satellite downlink; RX only | never |
| 1575 MHz GPS L1 | ✔ RNSS protected; RX only | **never — spoofing is felonious** |
| Cell downlink | ✔ RX only (also usually encrypted) | never |
| 145 MHz FM voice | may be ISS pass or amateur repeater; RX safe | with amateur license |

## When the puzzle says "transmit X"

Read the target frequency out of the prompt. If it's in the BLOCKED
list, the prompt is either testing whether you understand the funnel,
or it's asking for a wired-dummy-load exercise (the "TX" is
symbolic). Confirm with the puzzle author before wiring anything.
