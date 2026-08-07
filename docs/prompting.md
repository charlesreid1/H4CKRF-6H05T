# Prompting

How to actually talk to the H4CKRF co-pilot so it does what you want.

This isn't a general LLM guide — the model behind H4CKRF has a
specific system prompt, a specific tool schema, and a specific set of
things it's inclined to over- or under-do. This doc names those
patterns and gives you the templates that work.

Applies equally to `hackrf-agent chat` (the CLI REPL) and any MCP
host driving `hackrf-agent-mcp`. The MCP path has an additional
layer — the host's own model — but the tool schema and the funnel
are the same.

---

## What the model already knows

Its system prompt (see `src/hackrf_agent/ai/prompts.py`) tells it:

- It has one tool: `execute_command`.
- The full band-tier table and BLOCKED bands.
- Every action name and its required args.
- **Prefer `target_freq_hz` over `center_freq_hz`** for captures.
- Risk tiers exist and are enforced host-side, not by it.
- The corpus is authoritative for numeric claims — use
  `knowledge_lookup_*` verbs instead of free recall.

You do not need to re-tell it any of this. Repeating it in your
prompt burns tokens and sometimes confuses the model.

## What the model won't do on its own

- **Guess your intent from silence.** "Look at 433" is ambiguous.
  Sweep? Capture? Decode? Say the verb.
- **Reuse an old `iq_path` unless you name it.** Every turn is a
  fresh reasoning pass; if you did a capture 10 messages ago, cite
  the path.
- **Chain more than one tool call per response by default.** The
  model calls one tool, waits for the result, then decides next
  steps. If you want multi-step, either say so ("sweep then
  capture") or let it iterate turn by turn.
- **Compose a `transmit_iq` without a grant.** It will hit the
  elicitation prompt every time. Grant first, TX after.

---

## Prompt templates that work

### The mystery-frequency triage

```
I want to know what's on {FREQ_MHZ} MHz. Do the full first-60-seconds
triage from ctf_playbook.md: band lookup, short sweep, decide capture
vs replay, and report what you found. Stop after triage — I'll direct
the next step.
```

Why this works: names the goal (triage), names the doc that defines
the plan, and caps the scope. The model won't over-run into a 5-minute
capture.

### The "here's an IQ file, tell me what it is"

```
I have an IQ file at {ABSOLUTE_PATH}. It's .cs8 at {SAMPLE_RATE} Msps,
captured near {FREQ_MHZ} MHz. Please:
1. Read the summary
2. Classify modulation
3. Estimate symbol rate
4. Suggest the most likely decoder based on the classification
Do not decode yet — I want to see the classification first.
```

Why this works: gives the metadata the file doesn't carry (sample
rate, tune), enumerates steps, and puts a checkpoint before the
decoder call so you can catch a wrong classification early.

### The "decode this and tell me if it's real"

```
Please run {DECODER_NAME} on {IQ_PATH} at symbol_rate_hz={RATE}. If
the result has crc_ok=false or invalid_pairs > num_symbols/4, tell me
before assuming the decode is real.
```

Why this works: primes the model to look at the validity flags it
otherwise glosses over. The default failure mode is "declare victory
from a garbage decode."

### The "I need TX prepped"

```
I want to transmit {SOMETHING} at {FREQ_MHZ} MHz. Before you propose
transmit_iq: check knowledge_lookup_band to confirm it's not BLOCKED,
then tell me exactly what grant I need to issue for the TX to run at
LOW tier. Don't call transmit_iq yourself.
```

Why this works: forces the model to verify legality and articulate the
grant scope *before* it hits the elicitation wall. You get a
copy-pastable `hackrf-agent grant tx ...` command out of it.

### The "compare two captures"

```
Compare the bit patterns from these three captures:
1. {IQ_PATH_1}
2. {IQ_PATH_2}
3. {IQ_PATH_3}
All are 433.92 MHz, 2 Msps, 3 s each. Run decode_manchester on each
at symbol_rate_hz=2000, then tell me whether the bursts are identical
(fixed code), monotonically drifting (rolling counter), or different
in a non-counter way (novel).
```

Why this works: gives it the multi-step task explicitly, names the
comparison criteria, and pre-labels the outcomes so the model doesn't
have to invent taxonomy on the fly.

---

## Steering: get it off recall, onto the corpus

The model has plenty of RF knowledge from training, and it will
happily hallucinate frequency numbers, band-plan details, or protocol
framing when you don't force it to look things up.

**Symptoms** of a recall-only answer:

- No `knowledge_lookup_*` call in the tool-call log.
- Specific numbers that don't cite a source ("POCSAG uses 512 baud"
  — is that all POCSAG? What if it's 1200?).
- Vendor-specific claims ("Chamberlain rolling code uses...") without
  a `knowledge_lookup_keyfob` call.

**Fixes:**

1. **Name the tool.** "Use `knowledge_lookup_protocol` to check the
   baud, don't guess." The model responds well to being pointed.
2. **Ask it to cite.** "For every numeric claim, tell me which
   `knowledge_*` verb produced it." This is the most reliable way
   to catch fabricated numbers.
3. **Reject uncited claims.** If a claim in its response doesn't
   cite the corpus, ask "where did that number come from?" — the
   model will either produce the tool call it should have made, or
   admit it guessed.

The trap catalog in `knowledge_verify_claim` exists specifically for
this. If a claim survives that check, it's probably real; if it
doesn't, the model *is* being tempted by a well-known trap.

---

## Steering: get it out of "one call and stop" mode

The default is: model calls one tool, sees the result, writes a
paragraph, and stops. That's usually right — you review before the
next step. But sometimes you want a chain.

**Yes-chain prompts:**

- "Do the full triage sequence I listed. Don't stop between steps."
- "After the sweep, capture immediately if you see a signal within
  ±5 dB of the peak in `records/known_signals.json`."
- "Iterate until you either decode a valid frame (crc_ok=true) or
  have exhausted decode_manchester, decode_pwm, and decode_ppm."

**No-chain prompts** (default behavior — you rarely need to force
this, but sometimes):

- "Just report the sweep results — no capture yet."
- "Stop after the classification. I want to review before decoding."

## Steering: get it to abort

Two ways to stop a runaway plan mid-flight:

1. **Ctrl-C once.** Kills the current tool call, revokes grants,
   dumps you back to the REPL / lets the MCP host recover.
2. **Type a new message.** The model can't ignore new input; it will
   incorporate the new direction on the next turn. Effective for
   pivoting without aborting: "wait — sweep 868 first before
   capturing."

If Ctrl-C didn't stop it and a new message didn't redirect it,
something is wrong. That's a bug, not a prompting issue.

---

## When the model refuses

Two flavors:

### The gate refused, not the model

Error message includes "BLOCKED" or names a specific band. This is
`RiskAssessor` doing its job — the model didn't refuse, the host did.
Read [safety.md](safety.md); this is not a prompting problem.

### The model refused

The response starts with "I can't" or "I won't" and no tool call
happened. This is the model's own judgment — usually right (never
spoof ADS-B, GPS, etc.), occasionally wrong (over-cautious about
legitimate RX or ISM TX).

**If the refusal is wrong:**

- Rephrase to make the legality obvious: "I have a Part 97 amateur
  license" doesn't work (the model isn't a licensing authority),
  but "I've issued a `hackrf-agent grant tx` for this band and the
  operator has an active grant covering it — please proceed" often
  does, because the gate will enforce the grant claim anyway.
- Point at the tool: "Please attempt the `sweep_spectrum` call and
  let the host decide whether to allow it."

**If the refusal is right and you disagree:** you're probably wrong.
The BLOCKED band list is deliberate. Don't argue with it; find a
different path to the flag.

---

## Prompt hygiene for MCP hosts

If you're driving from Claude Code, Claude Desktop, Cursor, OpenCode,
etc., the host's own model reads your prompt and decides whether to
call an H4CKRF tool. A few notes:

- **Name the tool explicitly.** "Use `hackrf_sweep_spectrum`..." is
  more reliable than "please sweep the spectrum". Some hosts route
  to a different, wrong tool if the intent is ambiguous.
- **Watch the elicitation prompt.** MEDIUM/HIGH commands surface as
  elicitation prompts inside the host. If your host doesn't render
  them well, you'll miss the approval and the tool call will time
  out. See [mcp.md](mcp.md) for host-specific caveats.
- **Long IQ paths are context-heavy.** Session paths are ~100 chars
  each. If you're deep in a conversation, the model's context is
  already full of them; consider abbreviating in your prompt ("the
  capture from earlier at 433.92") — the model can look up the
  actual path via `audit_query`.
- **Justifications land in the audit log.** Whatever you say goes
  into the `justification` field on the tool call, and that lives in
  `~/.hackrf-agent/agent.db` forever. Don't type anything you don't
  want a future incident-response reader to see.

---

## Anti-patterns

### "Just try things"

```
Poke around 433 MHz and see what you find.
```

The model will call `sweep_spectrum` with default args, look at the
result, and describe what it saw in prose. That's usually fine, but
if you actually want a decode, you have to say so. "Poke around" is
not a plan.

### Reading the mind of the classifier

```
It looks like OOK to me but the classifier says FSK — override it.
```

Don't tell the model to override the classifier. Tell it to try
both decoders and report which validates:

```
The classifier says 2FSK but the shape looks OOK. Try both
decode_pocsag (at 512/1200/2400) and decode_manchester (at 2000).
Report crc_ok / invalid_pairs from each so we can pick.
```

### Multi-goal single-turn

```
Sweep 433, if there's a keyfob decode it, if it's rolling do RollJam,
if it's fixed replay it, if there's nothing look at 868, if 868 is
empty look at 915, and while you're at it check for POCSAG on the
paging band.
```

The model will either half-do it and lose track, or over-commit and
run five captures you didn't want. Break it into turns.

### Forgetting the grant

```
Transmit 1 second of the burst we decoded at 433.92 MHz.
```

If you don't have a grant, this will hit the elicitation prompt.
Every. Single. Time. Issue the grant first (in a terminal), *then*
ask.

### Assuming session state persists across sessions

```
Use the capture from yesterday.
```

Session dirs persist on disk but the *conversation* doesn't. Cite
the absolute path.

---

## Cross-references

- [ctf_recipes.md](ctf_recipes.md) — the walkthroughs you're
  prompting the model to execute
- [ctf_playbook.md](ctf_playbook.md) — the strategy the model
  already knows
- [../skills/hackrf/SKILL.md](../skills/hackrf/SKILL.md) — the
  skill file assistant hosts read to decide when to reach for
  H4CKRF at all
- [safety.md](safety.md) — why some refusals are correct
- [troubleshooting.md](troubleshooting.md) — when the tool call
  itself fails
