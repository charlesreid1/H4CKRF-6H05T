# CTF Recipes

End-to-end worked walkthroughs for the puzzle shapes that keep coming
back at RF village and OTA CTFs. Each recipe is a **transcript** you
can hand to a fresh operator: exact tool calls, expected shapes,
decision points if the first path fails.

If you want the *strategy* (how to read a spectrogram, when to reach
for which decoder), read [ctf_playbook.md](ctf_playbook.md) and
[rf_cheatsheet.md](rf_cheatsheet.md) first. This file is the
concrete counterpart.

Every recipe assumes:

- `hackrf-agent doctor` is green.
- The MCP server is attached to your host (or you're in
  `hackrf-agent chat`).
- You've read [safety.md](safety.md) and understand the funnel.

Tool calls below use the MCP verb name (e.g. `hackrf_sweep_spectrum`);
inside the chat CLI the underlying `action` is the un-prefixed name
(`sweep_spectrum`). Both call the same handler.

---

## Recipe 1 — Unknown keyfob at 433.92 MHz

**Puzzle shape.** You're handed "figure out this keyfob" and a rough
band. Goal: classify (fixed / rolling / novel), decode a burst, and
decide whether replay would work.

### Step 1 — Confirm the band is legal

```json
{"action": "knowledge_lookup_band",
 "args": {"freq_hz": 433920000}}
```

Expect a record naming ISM 433 MHz (Region 1). `blocked_tx=false`,
so TX is allowed under a grant if you need it later. If the response
came back with a protected band, stop here — this recipe assumes ISM
territory.

### Step 2 — Triage sweep

```json
{"action": "sweep_spectrum",
 "args": {"start_freq_hz": 433000000, "end_freq_hz": 434500000,
          "dwell_s": 1.0, "lna_gain_db": 24}}
```

You want to see one or two narrow spikes near 433.92 MHz, appearing
in short (30–100 ms) bursts. If the spectrum is flat, either the fob
isn't being pressed or you're too far from it. Move closer or raise
LNA gain (max 40 dB).

### Step 3 — Capture 3–5 bursts

Press the fob 3–5 times during the capture window. Use
`target_freq_hz` so the LO leakage lands off-signal:

```json
{"action": "capture_iq",
 "args": {"target_freq_hz": 433920000,
          "sample_rate_hz": 2000000,
          "duration_s": 5.0,
          "lna_gain_db": 24, "vga_gain_db": 20}}
```

Response includes `iq_path` under `~/.hackrf-agent/sessions/<id>/iq/`.
Reuse that path in every downstream call.

### Step 4 — Classify the modulation

```json
{"action": "analyze_iq_modulation",
 "args": {"iq_path": "<from step 3>",
          "sample_rate_hz": 2000000}}
```

For a typical 433 MHz keyfob you should see `OOK` (or `ASK-2`) as the
top-ranked family with reasonable confidence. If it says `2FSK`
you're not looking at a keyfob — you may have snagged an adjacent
weather station or the wrong band.

### Step 5 — Estimate symbol rate

```json
{"action": "analyze_iq_symbols",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 2000000,
          "min_rate_hz": 500, "max_rate_hz": 20000}}
```

Expect `symbol_rate_hz` near 2000 for most Manchester-encoded fobs,
or near 1000–1500 for PWM Chamberlain-style fobs.

### Step 6 — Decode a single burst

Manchester first (covers ~90% of 433 fobs):

```json
{"action": "decode_manchester",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 2000000,
          "symbol_rate_hz": 2000,
          "polarity": "ieee"}}
```

If `invalid_pairs > num_symbols / 4`, flip polarity to `"g.e.thomas"`.
If still bad, try PWM:

```json
{"action": "decode_pwm",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 2000000,
          "short_us": 400, "long_us": 800}}
```

### Step 7 — Compare consecutive bursts

If your capture caught 3+ presses, `decode_manchester` returns each
burst separately. Compare their bit patterns.

| Observation | Verdict |
|---|---|
| All bursts identical | Fixed-code. Replay works. Older HomeEasy, some legacy garage doors. |
| Bursts differ, counter-like drift | Rolling-code (Keeloq or derivative). Replay defeated by counter desync; RollJam still applies. |
| Bursts differ, no counter pattern | Novel or encrypted. Likely PKE (relay attack territory) or timestamp-based. |

### Step 8 — Cross-reference the vendor

```json
{"action": "knowledge_lookup_keyfob",
 "args": {"vendor": "Chamberlain"}}
```

The `records/keyfobs.json` corpus knows Chamberlain, Genie, LiftMaster,
Tesla PKE, and more. Trap catalog is in
[knowledge/ctf/unknown-keyfob.md](../knowledge/ctf/unknown-keyfob.md).

### If replay is the flag

You've decided fixed-code. Issue a grant *before* asking the model
to compose a TX:

```bash
hackrf-agent grant tx 433.05-434.79M --for 10m --max-gain 20
```

Then feed the decoded burst back through the transmit path. In-grant
TX is MEDIUM but the grant reclassifies it to LOW — no elicitation.

---

## Recipe 2 — POCSAG page hunt

**Puzzle shape.** A frequency in the paging bands (US 929–932 MHz or
VHF 138–174) is emitting the flag inside an alphanumeric payload.

### Step 1 — Sweep the paging channel

```json
{"action": "sweep_spectrum",
 "args": {"start_freq_hz": 929000000, "end_freq_hz": 932000000,
          "sample_rate_hz": 8000000, "dwell_s": 1.5}}
```

Look for **two parallel spectral lines separated by ~9 kHz** and
short bursts every few seconds. That's the 2FSK signature.

### Step 2 — Capture

```json
{"action": "capture_iq",
 "args": {"target_freq_hz": 929612500,
          "sample_rate_hz": 2000000,
          "duration_s": 5.0}}
```

Five seconds usually catches at least one batch header. Longer
captures explode on disk (10 MB/s at 2 Msps).

### Step 3 — Confirm 2FSK

```json
{"action": "analyze_iq_modulation",
 "args": {"iq_path": "<step 2>",
          "sample_rate_hz": 2000000}}
```

Top-ranked family should be `2FSK`. If it says `OOK` you're on the
wrong signal.

### Step 4 — Decode POCSAG at each baud

POCSAG runs at 512, 1200, or 2400 baud. The decoder doesn't guess —
you try each:

```json
{"action": "decode_pocsag",
 "args": {"iq_path": "<step 2>",
          "sample_rate_hz": 2000000,
          "baud": 1200}}
```

If the response has zero `messages`, retry with `baud: 512` then
`baud: 2400`. The right rate returns `messages: [{ric, function,
payload_numeric, payload_alpha}, ...]`.

### Step 5 — Read the payload

- `function=0` → numeric (BCD digits, no letters). Rare for flags
  unless the puzzle is "decode this phone number."
- `function=1|2|3` → alphanumeric. Flag lives in `payload_alpha`.

Common CTF patterns:

- Flag directly in `payload_alpha` of one message.
- Flag split across messages sorted by `ric` — assemble in order.
- Flag encoded in the RIC itself (e.g. `1337000` = "leet zero zero
  zero").

### Step 6 — If POCSAG fails, try FLEX

FLEX is **not** in the H4CKRF decoder set (4FSK, Reed-Solomon FEC).
Escalate to `multimon-ng` outside the agent:

```bash
# Convert the .iq file to raw audio at the correct rate, then:
multimon-ng -t raw -a FLEX /path/to/audio.raw
```

See [knowledge/multimon-ng/](../knowledge/multimon-ng/) for the
handoff details.

---

## Recipe 3 — LoRa CSS classification

**Puzzle shape.** You see diagonal streaks in a waterfall around 868
MHz (EU) or 915 MHz (US). The puzzle asks "what spreading factor,
bandwidth, and coding rate?" or wants the payload decoded.

### Step 1 — Confirm the band

```json
{"action": "knowledge_lookup_band",
 "args": {"freq_hz": 915000000}}
```

US 902–928 ISM. RX allowed everywhere.

### Step 2 — Wide sweep

```json
{"action": "sweep_spectrum",
 "args": {"start_freq_hz": 902000000, "end_freq_hz": 928000000,
          "sample_rate_hz": 20000000, "dwell_s": 1.5}}
```

LoRa transmissions are wideband (125/250/500 kHz) chirps. In a sweep
they show up as a wider-than-narrowband smear at intervals.

### Step 3 — Capture with a wide sample rate

```json
{"action": "capture_iq",
 "args": {"target_freq_hz": 915000000,
          "sample_rate_hz": 8000000,
          "duration_s": 2.0}}
```

You need at least 2× the LoRa bandwidth. 8 Msps covers 500 kHz LoRa
comfortably.

### Step 4 — Spectrogram to see the chirps

```json
{"action": "analyze_iq_spectrogram",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 8000000,
          "fft_size": 1024,
          "max_slices": 512}}
```

The response gives per-slice `peak_freq_hz` + `power_db`. Diagonal
streaks in `peak_freq_hz` over time = CSS chirps.

### Step 5 — Look up the modulation record

```json
{"action": "knowledge_lookup_modulation",
 "args": {"name": "LoRa"}}
```

The record includes spreading-factor ↔ symbol-rate relationships.
H4CKRF does **not** ship a native LoRa decoder — for full payload
decode, escalate to `gr-lora` or `sdrangel`. The recipe here ends at
classification.

### Step 6 — If the puzzle wants SF/BW/CR

Read [knowledge/lora/reference.md](../knowledge/lora/reference.md).
Formulas:

- Symbol duration = `2^SF / BW`
- Chirp slope = `BW^2 / 2^SF`

You can eyeball SF from the chirp duration in the spectrogram output.

---

## Recipe 4 — APRS packet on 144.39 MHz

**Puzzle shape.** VHF around 144.39 (NA) or 144.800 (EU). Puzzle wants
the AX.25 payload or a specific field (callsign, comment, position).

### Step 1 — Verify the band is legal for RX

```json
{"action": "knowledge_lookup_band",
 "args": {"freq_hz": 144390000}}
```

Amateur 2 m band. RX is fine everywhere; TX requires a license
regardless of what H4CKRF says.

### Step 2 — Sweep briefly

```json
{"action": "sweep_spectrum",
 "args": {"start_freq_hz": 144380000, "end_freq_hz": 144400000,
          "sample_rate_hz": 2000000, "dwell_s": 2.0}}
```

APRS is bursty — you may need to wait for a beacon.

### Step 3 — Capture at least 5 s

Beacons come every 30–300 s depending on the station. Capture
generously:

```json
{"action": "capture_iq",
 "args": {"target_freq_hz": 144390000,
          "sample_rate_hz": 2000000,
          "duration_s": 30.0}}
```

Note: 30 s at 2 Msps = 120 MB. Set `MAX_CAPTURE_MINUTES` for a
budget guardrail.

### Step 4 — Decode APRS

```json
{"action": "decode_aprs",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 2000000,
          "baud": 1200}}
```

Response includes decoded AX.25 UI frames with interpreted APRS
payloads (position, weather, message, etc.). If `frames` is empty
but the band is active, drop to raw AX.25:

```json
{"action": "decode_ax25",
 "args": {"iq_path": "<step 3>",
          "sample_rate_hz": 2000000,
          "baud": 1200}}
```

Bell-202 AFSK-1200 is the standard; 9600 baud FSK is the alternative
(uncommon on 144.390).

### Step 5 — Verify

```json
{"action": "knowledge_lookup_protocol",
 "args": {"name": "APRS"}}
```

Confirms framing and expected fields. If the flag is in a callsign
or message body, look for a Base91-encoded position or a `:` (message
delimiter) followed by the flag payload.

---

## Recipe 5 — Spectrogram stego

**Puzzle shape.** The puzzle *itself* is an IQ file (or waterfall
image). The flag is drawn as text/QR/image in the time-frequency
plane. No decoding required — just the right spectrogram.

### Step 1 — Take an IQ summary

```json
{"action": "read_iq_summary",
 "args": {"iq_path": "/path/to/mystery.iq",
          "center_freq_hz": 433920000,
          "sample_rate_hz": 2000000}}
```

Response gives duration, sample count, and a rough noise-floor
estimate. Confirms the file parses.

### Step 2 — Get a spectrogram

```json
{"action": "analyze_iq_spectrogram",
 "args": {"iq_path": "/path/to/mystery.iq",
          "sample_rate_hz": 2000000,
          "fft_size": 2048,
          "overlap": 0.5,
          "max_slices": 1024}}
```

Response is *summary data* (per-slice peak + power), not an image.
For a visual, open the file in Inspectrum or URH — see
[iq_handling.md](iq_handling.md) for the handoff.

### Step 3 — Look for structure

Stego patterns to watch for:

- **Text in the waterfall.** Letters drawn by tone-hopping over time.
- **QR code.** 2D pattern of on/off pixels across time and freq.
- **Barcode.** Vertical stripes at specific frequency offsets.
- **Morse.** Long/short bursts at a single frequency.
- **Hidden narrowband under a wideband cover.** Look at just the
  center bin.

### Step 4 — Extract if it's Morse

```json
{"action": "decode_ppm",
 "args": {"iq_path": "/path/to/mystery.iq",
          "sample_rate_hz": 2000000,
          "short_us": 100000,
          "long_us": 300000}}
```

Morse dot/dash ratios map to PPM short/long durations at CW rates
(typically 20–40 wpm, so dot ~30–60 ms).

### Step 5 — Cross-reference the trap catalog

Full patterns in [knowledge/ctf/waterfall-stego.md](../knowledge/ctf/waterfall-stego.md).

---

## Recipe 6 — Mystery-modulation IQ file

**Puzzle shape.** You're handed a `.iq` file with no metadata. The
puzzle is "figure out what this is." Your job: classify → decode →
extract flag.

### Step 1 — Read the summary

```json
{"action": "read_iq_summary",
 "args": {"iq_path": "/tmp/mystery.iq",
          "center_freq_hz": 0,
          "sample_rate_hz": 2000000}}
```

Confirms the file loads. If the puzzle didn't tell you the sample
rate, you'll have to guess — try 2 Msps first, then 8 Msps if the
spectrogram looks compressed on the time axis.

### Step 2 — Refine the carrier if the DC spike is on top of the signal

```json
{"action": "analyze_iq_carrier_frequency",
 "args": {"iq_path": "/tmp/mystery.iq",
          "sample_rate_hz": 2000000}}
```

Returns a parabolic-interpolated peak frequency offset in Hz relative
to whatever the file's center was. This unlocks decoders that
misfire when the actual carrier is offset from 0 Hz.

### Step 3 — Classify

```json
{"action": "analyze_iq_modulation",
 "args": {"iq_path": "/tmp/mystery.iq",
          "sample_rate_hz": 2000000}}
```

The classifier returns a ranked list. Trust the top entry only if
its confidence beats runners-up meaningfully; otherwise verify with
step 4.

### Step 4 — Symbol rate

```json
{"action": "analyze_iq_symbols",
 "args": {"iq_path": "/tmp/mystery.iq",
          "sample_rate_hz": 2000000,
          "min_rate_hz": 100}}
```

Consistent symbol rate estimates across the file are a strong
positive signal for the classification.

### Step 5 — Pick a decoder by top family

| Top family | Try first | Fallbacks |
|---|---|---|
| OOK / ASK-2 | `decode_manchester` (polarity: ieee) | `decode_pwm`, `decode_ppm`, `decode_nrz` |
| 2FSK | `decode_pocsag` (baud 512/1200/2400) | `decode_rtty`, `decode_ax25` |
| GFSK | `decode_ax25` (baud 9600) | (Bluetooth-shaped signals: escalate) |
| MFSK / 4FSK | (not in H4CKRF) | escalate to `multimon-ng` for FLEX |
| CSS (chirp) | (not in H4CKRF) | escalate to `gr-lora` |
| OFDM | (not in H4CKRF) | escalate to a full stack (WiFi/LTE tools) |

Also see the one-page selector in [rf_cheatsheet.md](rf_cheatsheet.md).

### Step 6 — Verify

If the decoder returns a "flag-shaped" payload, sanity-check it
against `knowledge_verify_claim` to make sure the framing you
believe is real is documented as real. A payload that starts with
`flag{` before validation is only 60% of the answer.

---

## When a recipe doesn't fit

- **Modulation not in the classifier.** OFDM (WiFi, LTE), 4FSK
  (FLEX), CSS variants — H4CKRF classifies but doesn't decode these.
  Escalate to `gr-` or dedicated tools; the corpus documents which.
- **Signal in a BLOCKED band.** Working as intended. GPS spoofing,
  ADS-B injection, aviation voice — you can't, and no CTF should ask
  you to. If the puzzle appears to require this, re-read the puzzle
  statement; the intended solution is almost always RX-only or
  synthesis-in-simulation.
- **You need TX to reproduce.** Issue the grant first. Never let the
  model compose a `transmit_iq` without a matching grant in place —
  it will hit the elicitation prompt every single time.

---

## Cross-references

- [ctf_playbook.md](ctf_playbook.md) — first-60-seconds strategy
- [rf_cheatsheet.md](rf_cheatsheet.md) — band + modulation tables
- [iq_handling.md](iq_handling.md) — file formats, cross-tool handoffs
- [prompting.md](prompting.md) — how to drive the copilot
- [knowledge/ctf/](../knowledge/ctf/) — full trap catalog per puzzle
  shape
