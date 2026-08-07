# rf-triage — the first 60 seconds

You've been handed a frequency, an IQ file, or a hint. What now?

## Step 1: Read the puzzle first, the radio second

Where does the flag live?

- **In the frequency.** Obscure allocation, band lookup wins.
- **In the modulation.** Unusual FSK deviation, unusual chirp rate.
- **In a decoded frame.** Text, hash, or QR inside a packet body.
- **In the timing.** Symbol period, Manchester bit width, PPM ratio.
- **In the interaction.** Replay, jam-then-capture, challenge/response.

Answer that first. It determines every tool call below.

## Step 2: Look at the band, not the radio

- `knowledge_lookup_band({freq_hz})` — is this ISM, blocked, or amateur?
- If BLOCKED for TX and the puzzle expects TX, either the flag lives
  in *just RX* (very likely for aviation/GNSS) or the challenge author
  made a mistake — never try to bypass the funnel.

## Step 3: Sweep before you capture

- `sweep_spectrum({start, end, dwell_s=1})` at LOW risk.
- Check the top-N peaks. Is there activity where the puzzle expects
  it? If the band is silent, the transmitter is off — no amount of
  cleverness recovers a signal that isn't there.

## Step 4: Capture at the right offset

- Use `target_freq_hz`, not `center_freq_hz`. The DC spike ruins
  captures tuned directly to the signal.
- Sample rate ≥ 4× signal bandwidth. Use 2 Msps as a safe default for
  narrow keyfob/paging bursts; jump to 8 Msps for wideband stuff.
- Duration: enough to catch at least 3-5 bursts. Keyfobs repeat 3-5×
  per press; POCSAG has multi-second gaps between messages.

## Step 5: Classify + measure symbol rate

- `analyze_iq_modulation(iq_path)` → family (OOK / FSK / GFSK / PSK)
- `analyze_iq_symbols(iq_path)` → symbol rate
- Cross-check against `records/known_signals.json` via
  `knowledge_explain_signal({freq_hz, bw_hz, modulation_guess})`.

## Step 6: Decode

Pick the decoder that matches the classification. If the first pick
returns `invalid_pairs > num_symbols/4` or `crc_ok == false`:

1. Flip polarity.
2. Try the sibling decoder (Manchester ↔ PWM, NRZ ↔ NRZI).
3. Recapture at a higher sample rate.
4. Look for a documented framing you missed.

## When to stop

- The flag is in your hand.
- Budget cap reached (`MAX_CAPTURE_MINUTES`).
- The puzzle needs TX in a BLOCKED band — the puzzle is either
  RX-only or misspecified.

## The failure modes

- **You forgot the DC spike.** Every recapture with `target_freq_hz`
  instead of `center_freq_hz` avoids a class of "no signal" errors.
- **You confused Manchester symbol rate with bit rate.** Manchester's
  symbol rate is 2× the bit rate. `analyze_iq_symbols` reports the
  bit rate (edge-interval detector), not the Manchester symbol rate.
- **You forgot to check `crc_ok`.** A "decoded" frame with a bad CRC
  is not decoded — try recapturing with more gain, or with a longer
  duration.

## Cross-references

- `../iq-analysis/walkthrough.md` — worked example of the pipeline
- `../modulation/recognition.md` — what each family looks like
- `../../docs/ctf_playbook.md` — the operator's quick reference
