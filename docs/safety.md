# Safety Policy & Frequency Reference

**This document is the source of truth for `frequency_policy.py` and `risk_assessor.py`.**
Every band, every citation, every rule those modules enforce is transcribed from this document.
Implementation is transcription, not judgment.

---

## Disclaimer

**HackRF One is a software-defined radio capable of transmitting on frequencies from
1 MHz to 6 GHz.** This software gates commands through a deterministic risk assessor,
but it cannot guarantee legal compliance. The operator (you) is responsible for:

1. Knowing and following all applicable laws in your jurisdiction.
2. Verifying that any transmission is authorized before approving it.
3. Understanding that the AI model is a statistical text generator, not an RF engineer or a lawyer.

**If you transmit on a frequency you are not authorized to use, you are liable for the
consequences, regardless of what this software or its AI backend told you.**

---

## Blocked Bands — Absolute Prohibitions

These frequency ranges are **BLOCKED for all actions** (RX and TX alike in some cases,
always for TX). The `frequency_policy.py` module encodes these as `BLOCKED_BANDS`.

### Aviation Safety-of-Life Bands

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **ADS-B / SSR / TCAS** | 1087–1093 MHz (1090 ± 3 MHz) | 47 CFR §87.131–147; ICAO Annex 10 Vol IV | ADS-B (1090 MHz), SSR, and TCAS/ACAS share this frequency. All civilian airliners broadcast position and receive collision-avoidance data here. Interference is a direct threat to flight safety. |
| **Aviation VHF Voice** | 118.000–137.000 MHz | 47 CFR §87.171–173; ICAO Annex 10 Vol V | Civil aviation voice communications (AM, 25 kHz and 8.33 kHz channels). Includes air traffic control, tower, ground, approach/departure, and emergency (121.5 MHz guard). |
| **VHF Guard (Emergency)** | 121.400–121.600 MHz (121.5 ± 100 kHz) | ICAO Annex 10 Vol V | International aeronautical emergency frequency. Military uses 243.0 MHz (UHF guard, harmonic of 121.5). |

### GNSS / Satellite Navigation Bands

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **GPS L1** | 1559–1591 MHz (1575.42 MHz center) | ITU RR Article 5 (RNSS allocation); 47 CFR Part 87 | GPS C/A code, P(Y) code, and modernized L1C. Civilian receivers worldwide depend on this signal. |
| **GPS L2** | 1215–1240 MHz (1227.60 MHz center) | ITU RR; 47 CFR Part 87 | GPS L2C and P(Y) code. Augments L1 for dual-frequency receivers. |
| **GPS L5** | 1164–1189 MHz (1176.45 MHz center) | ITU RR | Safety-of-life signal for aviation. Newer satellites. |
| **GLONASS G1** | 1592.9525–1610.485 MHz | ITU RR | Russian GNSS constellation G1 band. |
| **GLONASS G2** | 1237.8275–1254.4275 MHz | ITU RR | Russian GNSS constellation G2 band. |
| **Galileo E1** | 1559–1591 MHz | ITU RR | European GNSS (shares GPS L1). |
| **Galileo E6** | 1260–1300 MHz | ITU RR | European GNSS (commercial service). |
| **BeiDou B1** | 1559.052–1591.788 MHz | ITU RR | Chinese GNSS. |

### Maritime Distress & Safety

| Band | Frequency Range | Authority | Reason |
|------|----------------|-----------|--------|
| **VHF Ch 16 (Distress)** | 156.7625–156.8375 MHz (156.8 ± 37.5 kHz) | 47 CFR §80.369; ITU RR Appendix 18 | International maritime distress, safety, and calling frequency. Monitored by all coast stations and SOLAS vessels. |
| **VHF Ch 70 (DSC)** | 156.525 MHz | ITU RR Appendix 18 | Digital Selective Calling — automated distress alerting. |
| **MF/HF Distress** | 2182 kHz, 4125 kHz, 6215 kHz, 8291 kHz, 12290 kHz, 16420 kHz | ITU RR | Maritime distress and safety HF frequencies. HackRF's minimum is 1 MHz, so 2182 kHz is within range. |

### Cellular Downlink Bands (US)

Transmitting on cellular downlink interferes with mobile devices receiving base-station signals.
All are **BLOCKED for TX**.

| Band | Uplink (UE → Tower) | Downlink (Tower → UE) | FCC Rule Part | Carrier Usage |
|------|---------------------|----------------------|---------------|---------------|
| **Band 2** (PCS 1900) | 1850–1910 MHz | **1930–1990 MHz** | 47 CFR Part 24E | AT&T, Verizon, T-Mobile |
| **Band 4** (AWS) | 1710–1755 MHz | **2110–2155 MHz** | 47 CFR Part 27 | AT&T, Verizon, T-Mobile |
| **Band 5** (Cell 850) | 824–849 MHz | **869–894 MHz** | 47 CFR Part 22H | AT&T, US Cellular |
| **Band 12** (700 Lower) | 699–716 MHz | **729–746 MHz** | 47 CFR Part 27 | AT&T, T-Mobile |
| **Band 13** (700 Upper C) | 777–787 MHz | **746–756 MHz** | 47 CFR Part 27 | Verizon (primary) |
| **Band 17** (700 Lower B/C) | 704–716 MHz | **734–746 MHz** | 47 CFR Part 27 | AT&T |

**Additional blocked downlink ranges** (not exhaustive; the frequency policy module encodes
the full set):

- **600 MHz band** (Band 71): downlink 617–652 MHz (T-Mobile)
- **2300 MHz band** (Band 30): downlink 2350–2360 MHz (AT&T)
- **2500 MHz band** (Band 41): 2496–2690 MHz (TDD — both directions blocked)
- **CBRS** (Band 48): 3550–3700 MHz (shared, but blocked for TX out of caution)

### Emergency Services

| Band | Frequency Range | Reason |
|------|----------------|--------|
| **Public Safety 700 MHz** | 758–769 MHz, 788–799 MHz (narrowband), 769–775 MHz, 799–805 MHz (broadband) | FirstNet and public safety LTE |
| **VHF Public Safety** | 150.8–156.2475 MHz, 157.1875–161.575 MHz | Police, fire, EMS VHF allocations (varies by locality) |
| **UHF Public Safety** | 453.0–454.0 MHz, 460.0–460.6375 MHz | Public safety UHF |
| **800 MHz Public Safety** | 806–809 MHz, 851–854 MHz (NPSPAC) | Public safety 800 MHz |

### Radio Astronomy & Passive Services

| Band | Frequency Range | Reason |
|------|----------------|--------|
| **Hydrogen line** | 1400–1427 MHz (1420.40575177 MHz center) | Protected passive band — radio astronomy. The 21 cm hydrogen line is one of the most important frequencies in radio astronomy. TX is prohibited internationally. |
| **Radio astronomy** | 406.1–410.0 MHz, 608–614 MHz, 1335–1350 MHz, 2690–2700 MHz, 4990–5000 MHz | ITU-R RA.769 protected radio astronomy bands. |

---

## ISM Bands — Permitted for Unlicensed Operation (FCC Part 15)

These bands are available for low-power unlicensed devices under FCC Part 15 rules.
The HackRF agent treats these as **default-allowed for RX; TX is MEDIUM-tier if within
band and legal power limits, HIGH-tier otherwise.**

| Band | Frequency Range | Applicable FCC Rule | Notes |
|------|----------------|---------------------|-------|
| **315 MHz** | 310–320 MHz (center 315 MHz) | 47 CFR §15.231 | Periodic transmitters only (keyfobs, garage doors, tire pressure sensors). Field strength limit: 6,041–6,417 µV/m at 3 m (fundamental). Transmission must be manually initiated and cease within 5 seconds. |
| **433 MHz ISM** | 433.05–434.79 MHz | 47 CFR §15.231 (US); ETSI EN 300 220 (EU, Region 1 ISM) | ISM Region 1 band. In the US, falls under §15.231's 260–470 MHz general periodic-transmitter rules. Much wider allowed operation in EU (433.05–434.79 MHz ISM). LoRa, Amateur radio secondary. |
| **902–928 MHz** | 902.000–928.000 MHz | 47 CFR §15.247 (FHSS/DSSS, up to 1 W conducted); §15.249 (narrowband, 50 mV/m @ 3 m) | The main US ISM band below 2.4 GHz. LoRa, Z-Wave, amateur radio (33 cm band, secondary). Amateur allocation is 902.000–928.000 MHz exactly. |
| **2.4 GHz** | 2400.0–2483.5 MHz | 47 CFR §15.247 (up to 1 W); §15.249 | Wi-Fi, Bluetooth, Zigbee, amateur (13 cm band 2300–2450 MHz, with 2400–2450 for satellite and broadband). |
| **5.8 GHz** | 5725.0–5875.0 MHz | 47 CFR §15.247; §15.249 | Upper ISM band. Wi-Fi 5 GHz (U-NII-3), some amateur operation. |

---

## Amateur Radio Allocations (47 CFR Part 97)

These are amateur (ham) bands that overlap with HackRF's frequency range.
Operating here requires a valid amateur radio license. **The HackRF agent cannot
substitute for a license — but these bands are not BLOCKED by default because
licensed operators may use them.** The risk is HIGH for TX in amateur bands
without explicit user grants.

| Band Name | Frequency Range | Notes |
|-----------|----------------|-------|
| **1.25 m** | 222–225 MHz | US-only amateur band. |
| **70 cm** | 420–450 MHz | Amateur primary. 433.00–435.00 MHz = auxiliary/repeater links. Shared with government radiolocation; amateur is secondary in some sub-bands. |
| **33 cm** | 902–928 MHz | Amateur secondary to ISM and government. ARRL band plan divides into weak-signal (902.0–903.4), mixed (903.4–909.0), broadband (909.0–927.0), repeater outputs (927.0–928.0). |
| **23 cm** | 1240–1300 MHz | Amateur primary. Overlaps with GPS L2 (1227.60 MHz). Amateurs must not interfere with RNSS. |
| **13 cm** | 2300–2450 MHz | Amateur secondary in 2300–2310; primary in 2390–2450 (but 2400–2450 overlaps ISM). 2310–2390 is non-amateur (Part 27 WCS). |

---

## Risk-Tier Ladder

This is the deterministic classification applied by `risk_assessor.py` to every command.
The LLM never assigns its own tier.

| Tier | Meaning | Criteria | Examples |
|------|---------|----------|----------|
| **LOW** | Auto-execute, no confirmation | Read-only, bounded duration, no disk write outside session dir | `get_device_info`, `sweep_spectrum` (RX, ≤2 s dwell), short `capture_iq` (≤5 s, to session path), `grant_list`, `audit_query` |
| **MEDIUM** | Single-key confirmation (Y/n) | Longer capture, higher gain, disk writes, TX in ISM bands within legal power | `capture_iq` >5 s, `transmit_iq` on 433.05–434.79 MHz with gain ≤ 30 dB, long `sweep_spectrum` (dwell > 2 s) |
| **HIGH** | Must type CONFIRM | TX anywhere non-trivial, high gain, long TX, TX outside ISM but not blocked, any TX without an active grant | `transmit_iq` with gain > 30 dB, TX on 315 MHz (higher power), TX on amateur bands, any `transmit_iq` above +30 dB total gain |
| **BLOCKED** | Refused, no appeal | Protected bands (see Blocked Bands table), illegal ranges, TX gain exceeds hardware maximum (47 dB) | TX on 1090 MHz, 1575 MHz, 156.8 MHz, cellular downlink, aviation voice, GPS bands, TX VGA gain > 47 dB |

### Gain Caps

HackRF One has three gain stages:

| Stage | Range | Step Size | Notes |
|-------|-------|-----------|-------|
| **RF Amp** | 0 or 14 dB | 14 dB | On/off. Enable for weak signals. |
| **LNA (RX)** | 0–40 dB | 8 dB | RX only. `lna_gain_db` clamped to {0, 8, 16, 24, 32, 40}. |
| **VGA (RX)** | 0–62 dB | 2 dB | RX baseband gain. |
| **VGA (TX)** | 0–47 dB | 1 dB | TX IF gain. **Capped at 47 dB by the risk assessor.** |

The `risk_assessor.py` caps `tx_vga_gain_db` at 47 dB (hardware maximum) and applies an
additional policy cap of 30 dB for MEDIUM-tier TX. Transmitting at >30 dB TX VGA gain
forces HIGH tier.

---

## Plain-English Risk Tiers

What each tier means for you, the operator:

- **LOW** — "Reads only." Sweep the spectrum; check device info; list grants;
  query the audit log. The agent will just do it — no prompt, no pause. These
  actions do not transmit and do not write outside the session directory.

- **MEDIUM** — "Longer captures, TX in known-safe hobby bands within an active
  grant." You'll be asked once. Type `Y` or `n` at the prompt. If you're unsure,
  type `n` — the agent will propose an alternative.

- **HIGH** — "TX in bands where you haven't issued a grant, or at higher power."
  You'll be asked to type the literal word `CONFIRM`. This is intentional — it
  prevents muscle-memory approval. Do not autocomplete. Read the justification
  and expected effect before typing.

- **BLOCKED** — "Protected bands." The agent cannot do this. If it tries, the
  gate refuses and audits the attempt. No prompt — just a refusal. If the agent
  keeps proposing blocked actions, it may be prompt-injected; end the session.

---

## The Grant Model

Grants are scoped, time-limited permissions you issue explicitly. They tell the
risk gate "I pre-authorize TX in this band at up to this gain for this long."

```bash
hackrf-agent grant tx 433.05-434.79M --for 30m --max-gain 30
```

What a grant **does:**
- Lets the agent proceed with TX in the granted band at the granted gain without
  per-command approval (reclassifies from MEDIUM/HIGH to LOW within scope).
- Has a hard TTL — after expiry, transmissions revert to their un-granted tier.
- Can be revoked at any time with `hackrf-agent grant revoke <id>`.

What a grant **does NOT do:**
- Does **not** authorize you legally to transmit. You are responsible for your
  own FCC (or local) compliance.
- Does **not** override BLOCKED bands. A grant on 1090 MHz is impossible — the
  frequency policy refuses it before the grant is created.
- Does **not** survive a kill-switch event. Ctrl-C revokes all TX grants.

---

## The Kill Switch

Ctrl-C is the kill switch. It has two levels:

1. **Single Ctrl-C** — graceful abort of the current command. Sets the driver's
   `stop_event`, cancels the current asyncio task, and **revokes all TX grants**.
   The agent remains running; you can issue new grants and continue.

2. **Double Ctrl-C** (within 2 seconds) — hard exit. The process terminates
   immediately. TX may continue for a few milliseconds while the hardware buffer
   drains; unplug HackRF if this is unacceptable.

The kill-switch logic lives in `src/hackrf_agent/cli/kill_switch.py`. After any
Ctrl-C event, TX is frozen until you explicitly re-issue a grant with
`hackrf-agent grant tx ...`.

---

## Session Budgets (`MAX_CAPTURE_MINUTES`, `MAX_TX_SECONDS`)

Belt-and-suspenders to the per-command duration limits enforced by
`RiskAssessor`. Where the per-command tier stops "one 30-minute
capture," the session budget stops "sixty 30-second captures summing
to 30 minutes." Both budgets are per-executor-instance (i.e. per
session); restarting the process resets the counters.

### Capture budget

When `MAX_CAPTURE_MINUTES` is set in the environment (positive number,
e.g. `10` or `1.5`), the cumulative sum of every `capture_iq` call's
`duration_s` in the session must stay under that cap. Any call that
would push the total over is refused with `BLOCKED` before any RF
activity — the driver is never invoked.

```bash
export MAX_CAPTURE_MINUTES=10
hackrf-agent chat
# Cumulative capture_iq duration in this session is capped at 600 seconds.
```

The cap applies only to `capture_iq`; `sweep_spectrum` and
`sweep_spectrum_bulk` are not affected.

### TX budget

When `MAX_TX_SECONDS` is set (positive number, e.g. `60`), the
cumulative TX time across every `transmit_iq` call in the session must
stay under that cap. Pre-flight estimates the requested TX duration
from the `.iq` file size and `sample_rate_hz` (interleaved cs8 =
2 bytes/sample); the driver-measured duration is charged on success.
A TX that would push the total over the cap is `BLOCKED` before the
driver is invoked, with a matching audit row.

```bash
export MAX_TX_SECONDS=60
hackrf-agent chat
# Cumulative transmit_iq on-air time in this session is capped at 60 seconds.
```

Both budgets are **disabled by default** — leave them unset for a
per-command-only cap. Set them explicitly for a bounded session.

---

## What This Software Does NOT Protect Against

- **Prompt injection.** A compromised or adversarial prompt can propose bad
  commands. The risk gate still refuses BLOCKED actions, but a malicious prompt
  could exhaust your API budget by proposing thousands of LOW actions, or could
  social-engineer you into approving a HIGH TX. Read the `justification` field
  before approving. If it doesn't match what you asked, deny.

- **Prompt-level guidance is a hint; only the risk gate is enforcement.** The
  system prompt tells the model to be cooperative, but the model is a statistical
  text generator. The Python code in `risk_assessor.py` and `frequency_policy.py`
  is the only thing that can actually refuse a command.

- **Editing `frequency_policy.py` weakens the gate.** If you add a band to
  `ISM_BANDS` or remove it from `BLOCKED_BANDS`, the gate will allow what you
  told it to allow. You own that decision. Review any diff to
  `frequency_policy.py` as if it were a firewall rule change — because it is.

- **Hardware failure.** If the HackRF's PA (power amplifier) fails in a way that
  causes spurious emissions, the software gate cannot detect or prevent it. The
  gate operates at the command level, not the RF level.

---

## Incident Response

If TX went out on a frequency it shouldn't have:

1. **Unplug HackRF immediately.** Physical air-gap is the fastest stop.
2. **Reconstruct the session:**
   ```bash
   hackrf-agent audit tail --trace <trace_id>
   ```
   This shows every event for that command: what was requested, what the risk
   assessment was, whether approval was granted, and the result.
3. **File an issue** with the audit dump attached. Include the full `audit tail`
   output for the session. Redact your API key if it appears (it shouldn't — the
   audit log does not store credentials).

---

## References

- **FCC Part 15** (Radio Frequency Devices): [ecfr.gov — 47 CFR Part 15](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15)
  - §15.209 — General radiated emission limits
  - §15.231 — Periodic operation in the band 40.66–40.70 MHz and above 70 MHz
  - §15.247 — Operation within the bands 902–928 MHz, 2400–2483.5 MHz, and 5725–5850 MHz
  - §15.249 — Operation within the bands 902–928 MHz, 2400–2483.5 MHz, 5725–5875 MHz, and 24.0–24.25 GHz
- **FCC Part 87** (Aviation Services): [ecfr.gov — 47 CFR Part 87](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-87)
- **FCC Part 80** (Maritime Services): [ecfr.gov — 47 CFR Part 80](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-80)
- **FCC Part 97** (Amateur Radio Service): [ecfr.gov — 47 CFR Part 97](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97)
- **FCC Part 22** (Public Mobile Services): Cellular 850 MHz band
- **FCC Part 24** (Personal Communications Services): PCS 1900 MHz band
- **FCC Part 27** (Miscellaneous Wireless Communications Services): AWS, 700 MHz, 2300 MHz, 600 MHz bands
- **ARRL Band Plan**: [arrl.org/band-plan](https://www.arrl.org/band-plan)
- **ITU Radio Regulations**: [itu.int/pub/R-REG-RR](https://www.itu.int/pub/R-REG-RR)
- **ICAO Annex 10** (Aeronautical Telecommunications): Vol IV (Surveillance Radar), Vol V (Aeronautical Radio Frequency Spectrum Utilization)
- **HackRF One Hardware**: [greatscottgadgets.com/hackrf/one/](https://greatscottgadgets.com/hackrf/one/)
