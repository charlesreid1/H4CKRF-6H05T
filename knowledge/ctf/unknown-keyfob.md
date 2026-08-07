# unknown-keyfob — is it fixed, rolling, or novel?

You've captured 3-5 short OOK bursts at 315 or 433 MHz. Now what?

## Step 1: Confirm it's a keyfob

Cross-check against `records/known_signals.json`:

```
knowledge_explain_signal({
  "freq_hz": 433920000,
  "bw_hz": 40000,
  "modulation_guess": "OOK"
})
```

Should return `signal-ism-433-*` records. If not, it's not a keyfob —
try weather-station or garage-door.

## Step 2: Decode a single burst

Assume Manchester at 2 kbps first (weather stations and older keyfobs):

```
decode_manchester({iq_path, sample_rate_hz, symbol_rate_hz: 2000, polarity: "ieee"})
```

If `invalid_pairs > num_symbols/4`, flip polarity. If still bad, try
PWM with `short_us=400, long_us=800`.

## Step 3: Compare consecutive bursts

- **Fixed code.** All bursts decode to *identical* bit patterns.
  Replay works forever. Older HomeEasy/Nexa, some legacy garage
  doors.
- **Rolling code.** Bursts differ. If they differ by a monotonic
  counter (bit fields shift by 1 each press), you're looking at
  Keeloq or a Keeloq-derivative. Replay defeated by counter desync.
- **Novel / research-grade.** Bursts differ in ways that don't look
  like a counter. Could be encrypted challenge/response (PKE), a
  timestamp-based system, or a proprietary scheme.

## Step 4: Trap catalog

- "Rolling code defeats replay" → needs qualification. RollJam still
  works: jam the fob's transmission, capture it, unlock uses the
  captured code (which is still valid because the receiver never saw
  it), then replay the next capture on demand.
- "Keeloq is unbreakable" → false. Bogdanov 2007 slide attack;
  Eisenbarth 2008 side-channel.
- "Every keyfob is Manchester" → needs qualification. Many are PWM
  (Chamberlain, some Nexa).

## Step 5: Cross-reference the vendor

Use `knowledge_lookup_keyfob({vendor})` to see what's known about the
system. Chamberlain, Genie, Tesla, and PKE deployments all live in
`records/keyfobs.json`.

## Failure modes

- **Bursts don't decode as Manchester or PWM.** Consider that the
  encoding may be *layered* — some vendors put a preamble in
  Manchester and the payload in PWM, or vice versa.
- **Counter looks random.** It might not be a counter — it could be
  a nonce or a challenge from the car. If the fob only transmits
  after LF wakeup, you're seeing PKE; the "flag" is probably a relay
  attack demonstration, not a code recovery.

## Cross-references

- `../keyfobs/` — the full attack model
- `../garage-doors/` — Genie/Chamberlain/LiftMaster history
- `../crypto-in-rf/reference.md` — Keeloq / HITAG2 status
- `replay-vs-analyze.md` — deciding which strategy fits
